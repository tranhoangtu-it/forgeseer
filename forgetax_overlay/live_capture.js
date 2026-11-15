// Chạy bên trong tiến trình ForgeTax (nạp bởi Frida).
// Trên main thread của Unity (hook GPT6ForgeRoom.Update), định kỳ gọi hàm chụp trạng thái
// của chính game (trả về ForgeSavedRun - đúng class dùng để ghi file save), chuyển sang JSON
// bằng UnityEngine.JsonUtility rồi gửi ra ngoài. CHỈ ĐỌC: không ghi field nào của game.
//
// Tên hàm bị Obfuz làm rối nên hàm chụp được tìm theo chữ ký:
// hàm instance, 0 tham số, trả về ForgeSavedRun.
'use strict';

const GA = Process.getModuleByName('GameAssembly.dll');
const F = (n, r, a) => new NativeFunction(GA.getExportByName(n), r, a);
const api = {
  domain_get: F('il2cpp_domain_get', 'pointer', []),
  thread_attach: F('il2cpp_thread_attach', 'pointer', ['pointer']),
  domain_get_assemblies: F('il2cpp_domain_get_assemblies', 'pointer', ['pointer', 'pointer']),
  assembly_get_image: F('il2cpp_assembly_get_image', 'pointer', ['pointer']),
  image_get_name: F('il2cpp_image_get_name', 'pointer', ['pointer']),
  class_from_name: F('il2cpp_class_from_name', 'pointer', ['pointer', 'pointer', 'pointer']),
  class_get_methods: F('il2cpp_class_get_methods', 'pointer', ['pointer', 'pointer']),
  class_get_name: F('il2cpp_class_get_name', 'pointer', ['pointer']),
  class_from_type: F('il2cpp_class_from_type', 'pointer', ['pointer']),
  method_from_name: F('il2cpp_class_get_method_from_name', 'pointer', ['pointer', 'pointer', 'int']),
  method_get_return_type: F('il2cpp_method_get_return_type', 'pointer', ['pointer']),
  method_get_param_count: F('il2cpp_method_get_param_count', 'uint32', ['pointer']),
  method_get_flags: F('il2cpp_method_get_flags', 'uint32', ['pointer', 'pointer']),
  runtime_invoke: F('il2cpp_runtime_invoke', 'pointer', ['pointer', 'pointer', 'pointer', 'pointer']),
  class_get_fields: F('il2cpp_class_get_fields', 'pointer', ['pointer', 'pointer']),
  field_get_name: F('il2cpp_field_get_name', 'pointer', ['pointer']),
  field_get_type: F('il2cpp_field_get_type', 'pointer', ['pointer']),
  field_get_offset: F('il2cpp_field_get_offset', 'size_t', ['pointer']),
  field_get_flags: F('il2cpp_field_get_flags', 'int', ['pointer']),
  type_get_name: F('il2cpp_type_get_name', 'pointer', ['pointer']),
  field_static_get_value: F('il2cpp_field_static_get_value', 'void', ['pointer', 'pointer']),
  object_get_class: F('il2cpp_object_get_class', 'pointer', ['pointer']),
  string_new: F('il2cpp_string_new', 'pointer', ['pointer']),
  class_get_type: F('il2cpp_class_get_type', 'pointer', ['pointer']),
  type_get_object: F('il2cpp_type_get_object', 'pointer', ['pointer']),
};
const FIELD_ATTRIBUTE_STATIC = 0x10;
const METHOD_ATTRIBUTE_STATIC = 0x10;
const INTERVAL_MS = 300;
const MAX_FAILURES = 5;

api.thread_attach(api.domain_get());
const str = p => (p.isNull() ? '' : p.readUtf8String());

function image(name) {
  const count = Memory.alloc(8);
  const asms = api.domain_get_assemblies(api.domain_get(), count);
  for (let i = 0; i < count.readU64(); i++) {
    const img = api.assembly_get_image(asms.add(i * 8).readPointer());
    if (str(api.image_get_name(img)) === name) return img;
  }
  throw new Error('Không thấy assembly ' + name);
}

function klass(img, ns, name) {
  const k = api.class_from_name(image(img), Memory.allocUtf8String(ns), Memory.allocUtf8String(name));
  if (k.isNull()) throw new Error('Không thấy class ' + name);
  return k;
}

function methodByName(k, name, argc) {
  const m = api.method_from_name(k, Memory.allocUtf8String(name), argc);
  if (m.isNull()) throw new Error('Không thấy method ' + name);
  return m;
}

function findCaptureMethod(room) {
  const iter = Memory.alloc(8);
  iter.writePointer(NULL);
  let m;
  while (!(m = api.class_get_methods(room, iter)).isNull()) {
    const isStatic = (api.method_get_flags(m, NULL) & METHOD_ATTRIBUTE_STATIC) !== 0;
    const ret = str(api.class_get_name(api.class_from_type(api.method_get_return_type(m))));
    if (!isStatic && api.method_get_param_count(m) === 0 && ret === 'ForgeSavedRun') return m;
  }
  throw new Error('Không thấy hàm chụp ForgeSavedRun');
}

function invoke(m, obj, args) {
  const argv = Memory.alloc(8 * Math.max(args.length, 1));
  args.forEach((a, i) => argv.add(i * 8).writePointer(a));
  const exc = Memory.alloc(8);
  exc.writePointer(NULL);
  const result = api.runtime_invoke(m, obj, argv, exc);
  if (!exc.readPointer().isNull()) throw new Error('Game ném exception khi chụp trạng thái');
  return result;
}

// System.String của IL2CPP: độ dài int32 ở 0x10, ký tự UTF-16 từ 0x14.
const readManagedString = s => (s.isNull() ? null : s.add(0x14).readUtf16String(s.add(0x10).readS32()));

const room = klass('Assembly-CSharp.dll', '', 'GPT6ForgeRoom');
const capture = findCaptureMethod(room);
const toJson = methodByName(klass('UnityEngine.JSONSerializeModule.dll', 'UnityEngine', 'JsonUtility'), 'ToJson', 1);
const update = methodByName(room, 'Update', 0);

// ---------- tỉ lệ nhát kế tiếp (hàm tính tỉ lệ của game, đã gồm relic) ----------
function instanceFields(k) {
  const iter = Memory.alloc(8);
  iter.writePointer(NULL);
  const out = [];
  let f;
  while (!(f = api.class_get_fields(k, iter)).isNull()) {
    if (api.field_get_flags(f) & FIELD_ATTRIBUTE_STATIC) continue;
    out.push({ name: str(api.field_get_name(f)), type: str(api.type_get_name(api.field_get_type(f))),
               offset: Number(api.field_get_offset(f)) });
  }
  return out;
}
const roomFields = instanceFields(room);
const fieldOffset = name => {
  const f = roomFields.find(x => x.name === name);
  if (!f) throw new Error('Không thấy field ' + name);
  return f.offset;
};
const CAMPAIGN_OFF = fieldOffset('campaign');
// "CỐNG PHẨM PHẢI NỘP" của vòng hiện tại (field có tên rõ ràng của GPT6ForgeRoom).
const quotaField = roomFields.find(f => f.name === 'quota');
function readQuota(roomObj) {
  if (!quotaField) return 0;
  const p = roomObj.add(quotaField.offset);
  if (quotaField.type === 'System.Double') return p.readDouble();
  if (quotaField.type === 'System.Single') return p.readFloat();
  return p.readS32();
}
const BALANCE_OFF = fieldOffset('enhancementBalance');
// Mọi field GPT6Sword / List<GPT6Sword> của phòng rèn, trừ prefab mẫu.
const swordFields = roomFields.filter(f => f.type.includes('GPT6Sword') && f.name !== 'swordPrefab');
const SWORD = { serial: 36, broken: 105 };  // offset field của GPT6Sword (serial:int, broken:bool)
// $xA::$PH(GPT6Sword, ForgeCampaign, bool fever) -> struct 5 int (phần nghìn).
const oddsMethod = methodByName(klass('Assembly-CSharp.dll', '', '$xA'), '$PH', 3);
const ODDS_OFFSETS = [16, 20, 24, 28, 32];  // gãy, hỏng, giữ, thành công, đại thành công
const BALANCE_GRADE_MULTIPLIER_OFF = 32;    // ForgeEnhancementBalance.gradeMultiplier (float)

function liveSwords(roomObj) {
  const out = new Map();
  for (const f of swordFields) {
    const p = roomObj.add(f.offset).readPointer();
    if (p.isNull()) continue;
    let items = [p];
    if (f.type.includes('List<')) {
      const arr = p.add(16).readPointer();
      const n = p.add(24).readS32();
      items = arr.isNull() ? [] : [...Array(n).keys()].map(i => arr.add(32 + i * 8).readPointer());
    }
    for (const s of items) {
      if (s.isNull() || s.add(SWORD.broken).readU8()) continue;
      out.set(s.add(SWORD.serial).readS32(), s);
    }
  }
  return out;
}

function oddsFor(sword, campaign, fever) {
  const flag = Memory.alloc(4);
  flag.writeU8(fever ? 1 : 0);
  const boxed = invoke(oddsMethod, NULL, [sword, campaign, flag]);  // struct trả về dạng boxed
  return ODDS_OFFSETS.map(o => boxed.add(o).readS32());
}

function collectOdds(roomObj) {
  const campaign = roomObj.add(CAMPAIGN_OFF).readPointer();
  const odds = {};
  for (const [serial, s] of liveSwords(roomObj)) {
    odds[serial] = { normal: oddsFor(s, campaign, false), fever: oddsFor(s, campaign, true) };
  }
  const balance = roomObj.add(BALANCE_OFF).readPointer();
  const multiplier = balance.isNull() ? 1.5 : balance.add(BALANCE_GRADE_MULTIPLIER_OFF).readFloat();
  return { odds, multiplier };
}

// ---------- mô phỏng "nếu mua món trong shop" ----------
// Tạo một ForgeCampaign MỚI từ JSON (campaign hiện tại + relic định mua) bằng
// JsonUtility.FromJson rồi gọi lại hàm tính tỉ lệ của game. Campaign thật không bị đụng tới.
const jsonUtility = klass('UnityEngine.JSONSerializeModule.dll', 'UnityEngine', 'JsonUtility');
const fromJson = methodByName(jsonUtility, 'FromJson', 2);  // FromJson(string, Type)
const campaignType = api.type_get_object(api.class_get_type(klass('Assembly-CSharp.dll', '', 'ForgeCampaign')));
const SWORD_GRADE_OFF = 80;
let lastSimKey = '';

// Bản sao danh sách relic: thêm `addId` (đã có -> tăng rank; chỗ trống -> đặt vào) và/hoặc
// xóa ô `removeId` (để trống ô đó). Không đụng mảng gốc.
function editRelics(relics, { addId = null, removeId = null } = {}) {
  const out = relics.map(r => ({ ...r }));
  if (removeId) {
    const slot = out.find(r => r.id === removeId);
    if (slot) Object.assign(slot, { id: '', rank: 0 });
  }
  if (addId) {
    const owned = out.find(r => r.id === addId);
    const empty = out.find(r => !r.id);
    if (owned) owned.rank += 1;
    else if (empty) Object.assign(empty, { id: addId, rank: 1 });
    else out.push({ id: addId, rank: 1 });
  }
  return out;
}

// Tỉ lệ của mọi kiếm + tỉ lệ ở các grade mục tiêu với một campaign giả lập
// (tạo mới từ JSON; campaign thật giữ nguyên).
function simulate(campaign, relics, swords, target) {
  const json = api.string_new(Memory.allocUtf8String(JSON.stringify({ ...campaign, relics })));
  const fake = invoke(fromJson, NULL, [json, campaignType]);
  const perSword = {};
  for (const [serial, s] of swords) perSword[serial] = oddsFor(s, fake, false);
  return { perSword, byGrade: oddsAtGrades(fake, target) };
}

// Grade mục tiêu để chấm relic khi kiếm còn thấp (cộng thêm grade kiếm giá trị nhất).
const SHOP_TARGET_GRADES = [8, 12];
const BALANCE_BASE_VALUE_OFF = 24;  // ForgeEnhancementBalance.baseValue (double, =320)

function shopTarget(roomObj, swords, multiplier) {
  let g0 = 0;
  let topValue = -1;
  for (const s of swords.values()) {
    const v = s.add(SWORD_VALUE_OFF).readDouble();
    if (v > topValue) { topValue = v; g0 = s.add(SWORD_GRADE_OFF).readS32(); }
  }
  const balance = roomObj.add(BALANCE_OFF).readPointer();
  const base = balance.isNull() ? 320 : balance.add(BALANCE_BASE_VALUE_OFF).readDouble();
  const grades = [...new Set([...SHOP_TARGET_GRADES, ...(topValue > 0 ? [g0] : [])])].sort((a, b) => a - b);
  const valueAt = g => (topValue > 0 ? topValue * Math.pow(multiplier, g - g0) : base * Math.pow(multiplier, g));
  return { grades, valueAt };
}

function oddsAtGrades(campaignObj, target) {
  const out = {};
  for (const g of target.grades) out[g] = oddsAtGrade(campaignObj, g, target.valueAt(g), false);
  return out;
}

// ---------- bảng tỉ lệ theo grade (cho kế hoạch nhiều nhát) ----------
// $xA::$pH(int grade, ForgeCampaign, double value, bool fever) -> struct 5 int.
// Tự kiểm: tỉ lệ theo grade ở grade hiện tại phải khớp tỉ lệ thật của kiếm giá trị nhất.
const gradeOddsMethod = methodByName(klass('Assembly-CSharp.dll', '', '$xA'), '$pH', 4);
const SWORD_VALUE_OFF = 72;
const PLAN_GRADES_AHEAD = 14;

function oddsAtGrade(campaignObj, grade, value, fever) {
  const g = Memory.alloc(4);
  g.writeS32(grade);
  const v = Memory.alloc(8);
  v.writeDouble(value);
  const flag = Memory.alloc(4);
  flag.writeU8(fever ? 1 : 0);
  const boxed = invoke(gradeOddsMethod, NULL, [g, campaignObj, v, flag]);
  return ODDS_OFFSETS.map(o => boxed.add(o).readS32());
}

function gradeOddsTable(campaignObj, swords, multiplier) {
  let top = null;
  let topValue = -1;
  for (const s of swords.values()) {
    const v = s.add(SWORD_VALUE_OFF).readDouble();
    if (v > topValue) { top = s; topValue = v; }
  }
  if (top === null) return null;
  const g0 = top.add(SWORD_GRADE_OFF).readS32();
  const maxGrade = Math.max(...[...swords.values()].map(s => s.add(SWORD_GRADE_OFF).readS32())) + PLAN_GRADES_AHEAD;
  const valueAt = g => topValue * Math.pow(multiplier, g - g0);
  const valid = JSON.stringify(oddsAtGrade(campaignObj, g0, topValue, false)) ===
                JSON.stringify(oddsFor(top, campaignObj, false));
  const table = { valid, normal: {}, fever: {} };
  for (let g = 0; g <= maxGrade; g++) {
    table.normal[g] = oddsAtGrade(campaignObj, g, valueAt(g), false);
    table.fever[g] = oddsAtGrade(campaignObj, g, valueAt(g), true);
  }
  return table;
}

// Khi shop/relic/kiếm thay đổi: {shopSim:{buy,drop,swap}, gradeOdds}; không đổi -> null.
function simulateShop(roomObj, multiplier) {
  const campaignObj = roomObj.add(CAMPAIGN_OFF).readPointer();
  const campaign = JSON.parse(readManagedString(invoke(toJson, NULL, [campaignObj])));
  const relics = campaign.relics || [];
  const owned = relics.filter(r => r.id).map(r => r.id);
  const shelfFull = !relics.some(r => !r.id);
  const offerIds = campaign.shopping
    ? (campaign.offers || []).filter(o => o.id && !o.sold).map(o => o.id) : [];
  const swords = liveSwords(roomObj);
  const key = JSON.stringify([offerIds, relics,
    [...swords].map(([serial, s]) => [serial, s.add(SWORD_GRADE_OFF).readS32()])]);
  if (key === lastSimKey) return null;
  lastSimKey = key;

  const target = shopTarget(roomObj, swords, multiplier);
  const sim = { buy: {}, drop: {}, swap: {},
                grade: { base: oddsAtGrades(campaignObj, target), buy: {}, swap: {} } };
  for (const id of owned) {
    sim.drop[id] = simulate(campaign, editRelics(relics, { removeId: id }), swords, target).perSword;
  }
  for (const offer of offerIds) {
    const alreadyOwned = owned.includes(offer);  // mua trùng -> tăng rank, không cần chỗ
    if (!shelfFull || alreadyOwned) {
      const r = simulate(campaign, editRelics(relics, { addId: offer }), swords, target);
      sim.buy[offer] = r.perSword;
      sim.grade.buy[offer] = r.byGrade;
      continue;
    }
    sim.swap[offer] = {};
    sim.grade.swap[offer] = {};
    for (const id of owned) {
      const r = simulate(campaign, editRelics(relics, { removeId: id, addId: offer }), swords, target);
      sim.swap[offer][id] = r.perSword;
      sim.grade.swap[offer][id] = r.byGrade;
    }
  }
  return { shopSim: sim, gradeOdds: gradeOddsTable(campaignObj, swords, multiplier) };
}

// ---------- cống các ngày tới (forecastSchedule ở live_quota_schedule.js) ----------
// ForgeCampaign.$Gf() (instance, 0 tham số, double) = cống phải nộp của campaign (đã trừ
// tributeCredit, relic Khế Ước Trọn Đời...). Gọi trên campaign GIẢ LẬP tạo từ JSON với
// round+1 và tributeCredit = nextTributeCredit. Tự kiểm: campaign giả lập của hôm nay phải
// cho đúng `quota` của phòng rèn, lệch -> không gửi.
const QUOTA_METHOD = '$Gf';
const campaignClass = klass('Assembly-CSharp.dll', '', 'ForgeCampaign');
const quotaMethod = api.method_from_name(campaignClass, Memory.allocUtf8String(QUOTA_METHOD), 0);
const QUOTA_TOLERANCE = 0.5;

function fakeCampaign(campaign, overrides) {
  const json = api.string_new(Memory.allocUtf8String(JSON.stringify({ ...campaign, ...overrides })));
  return invoke(fromJson, NULL, [json, campaignType]);
}

function quotaOf(fake) {
  return invoke(quotaMethod, fake, []).add(16).readDouble();  // double trả về dạng boxed
}

// ---------- giá đổi lượt máy relic ----------
// Đọc chữ đang hiển thị (TextMesh.get_text - getter của Unity) của ForgeRelicVending.rerollText.
const VENDING_OFF = fieldOffset('vending');
let rerollTextOff = null;
let getTextMethod = null;

function readRerollText(roomObj) {
  const vending = roomObj.add(VENDING_OFF).readPointer();
  if (vending.isNull()) return '';
  if (rerollTextOff === null) {
    const f = instanceFields(api.object_get_class(vending)).find(x => x.name === 'rerollText');
    rerollTextOff = f ? f.offset : -1;
  }
  if (rerollTextOff < 0) return '';
  const mesh = vending.add(rerollTextOff).readPointer();
  if (mesh.isNull()) return '';
  if (getTextMethod === null) getTextMethod = methodByName(api.object_get_class(mesh), 'get_text', 0);
  return readManagedString(invoke(getTextMethod, mesh, [])) || '';
}

// ---------- tên + mô tả relic chính thức (bảng ngôn ngữ đã giải mã của game) ----------
// ForgeLocalization có field tĩnh Dictionary<lang, Dictionary<key, text>>; khóa relic:
// item.<id>.name / item.<id>.description. Chỉ đọc bộ nhớ, không gọi hàm của game.
const PREFERRED_LANG = 'vi';
const DICT_ENTRY_SIZE = 24;  // struct Entry { int hash; int next; TKey key; TValue value; }

function allFields(k) {
  const iter = Memory.alloc(8);
  iter.writePointer(NULL);
  const out = [];
  let f;
  while (!(f = api.class_get_fields(k, iter)).isNull()) {
    out.push({ f, name: str(api.field_get_name(f)), type: str(api.type_get_name(api.field_get_type(f))),
               offset: Number(api.field_get_offset(f)), isStatic: (api.field_get_flags(f) & FIELD_ATTRIBUTE_STATIC) !== 0 });
  }
  return out;
}

function dictEntries(dict) {
  const fs = allFields(api.object_get_class(dict));
  const entriesField = fs.find(f => /entries/.test(f.name));
  const countField = fs.find(f => /^_?count$/.test(f.name));
  if (!entriesField || !countField) return [];
  const arr = dict.add(entriesField.offset).readPointer();
  const n = dict.add(countField.offset).readS32();
  const out = [];
  for (let i = 0; i < n && !arr.isNull(); i++) {
    const e = arr.add(32 + i * DICT_ENTRY_SIZE);
    const key = e.add(8).readPointer();
    if (!key.isNull()) out.push([readManagedString(key), e.add(16).readPointer()]);
  }
  return out;
}

function readItemTexts() {
  const loc = klass('Assembly-CSharp.dll', '', 'ForgeLocalization');
  const tableField = allFields(loc).find(f => f.isStatic &&
    f.type.startsWith('System.Collections.Generic.Dictionary<System.String,System.Collections.Generic.Dictionary'));
  if (!tableField) return null;
  const buf = Memory.alloc(8);
  api.field_static_get_value(tableField.f, buf);
  if (buf.readPointer().isNull()) return null;
  const langs = new Map(dictEntries(buf.readPointer()));
  const lang = langs.has(PREFERRED_LANG) ? PREFERRED_LANG : [...langs.keys()][0];
  if (!lang) return null;
  const items = {};
  for (const [key, value] of dictEntries(langs.get(lang))) {
    const m = /^item\.(.+)\.(name|description)$/.exec(key || '');
    if (!m) continue;
    (items[m[1]] = items[m[1]] || {})[m[2]] = readManagedString(value);
  }
  return { lang, items };
}

let itemTexts = null;  // dùng lại ở live_relic_rank.js (danh sách relic ứng viên)
try {
  const texts = readItemTexts();
  itemTexts = texts;
  if (texts) send({ kind: 'texts', lang: texts.lang, items: texts.items });
} catch (e) {
  send({ kind: 'error', message: 'Không đọc được tên relic: ' + e });
}

let lastAt = 0;
let lastJson = '';
let failures = 0;
// MethodInfo->methodPointer nằm ở offset 0.
Interceptor.attach(update.readPointer(), {
  onEnter(args) {
    const now = Date.now();
    if (now - lastAt < INTERVAL_MS || failures >= MAX_FAILURES) return;
    lastAt = now;
    try {
      const run = invoke(capture, args[0], []);
      const json = readManagedString(invoke(toJson, NULL, [run]));
      const extra = collectOdds(args[0]);
      const changed = simulateShop(args[0], extra.multiplier);
      const quota = readQuota(args[0]);
      const reroll = json.includes('"shopping":true') ? readRerollText(args[0]) : '';
      const key = json + JSON.stringify(extra) + quota + reroll;
      const rank = collectRelicRank(args[0], extra.multiplier);  // live_relic_rank.js
      if (json && (key !== lastJson || changed || rank)) {
        lastJson = key;
        const schedule = forecastSchedule(args[0], quota);  // live_quota_schedule.js
        const message = { kind: 'run', json, odds: extra.odds, multiplier: extra.multiplier, quota,
                          nextQuota: schedule.length ? schedule[0] : 0, quotaSchedule: schedule,
                          rerollText: reroll };
        if (changed) {
          message.shopSim = changed.shopSim;
          if (changed.gradeOdds) message.gradeOdds = changed.gradeOdds;
        }
        if (rank) message.relicRank = rank;
        send(message);
      }
    } catch (e) {
      failures++;
      send({ kind: 'error', message: String(e) + (failures >= MAX_FAILURES ? ' (tạm dừng đọc trực tiếp)' : '') });
    }
  },
});
send({ kind: 'ready' });
