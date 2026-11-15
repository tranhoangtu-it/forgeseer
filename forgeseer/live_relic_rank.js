// Xếp hạng relic theo mức giảm tỉ lệ gãy - nối SAU live_capture.js thành một script Frida,
// dùng lại helper của file đó: invoke, toJson, readManagedString, fakeCampaign, editRelics,
// oddsAtGrade, itemTexts, CAMPAIGN_OFF, BALANCE_OFF, BALANCE_BASE_VALUE_OFF.
//
// Với mỗi relic chưa có: campaign GIẢ LẬP (JsonUtility.FromJson) = campaign hiện tại + relic đó
// (kệ đầy vẫn thêm để ước lượng), gọi $pH(grade, fake, baseValue*hệ số^grade, false) ở +8/+12/+16.
// Chỉ chạy lại khi bộ relic đổi; chia nhỏ qua nhiều lần Update để không giật khung hình.
// Kết quả: {baseline:{g:[5]}, items:{id:{g:[5]}}, owned:{id:{g:[5]}}, shelfFull} - owned = khi BỎ relic.

const RANK_GRADES = [8, 12, 16];
const RANK_BATCH = 12;  // số campaign giả lập mỗi lần Update
// Không phải relic đặt trên kệ: hàng Thương nhân ma, đồ dùng ngay / tiêu hao, phiếu vĩnh viễn,
// món "Tạm ngừng cung cấp".
const NON_SHELF_IDS = new Set([
  'ward', 'rewind', 'sword', 'worldtree', 'knife', 'starshard', 'powder', 'candle', 'chalk', 'oil',
  'steelcore', 'echodust', 'oblivion', 'contractink', 'delivery', 'creditshelf',
  'ticketdamage', 'tickethold', 'ticketsuccess', 'ticketgreat', 'ledger', 'safe',
]);
const NON_SHELF_TEXT = /Dùng ngay|không chiếm ô di vật|Tạm ngừng cung cấp/i;
// Giảm gãy theo điều kiện lúc rèn -> mô phỏng tĩnh không thấy; Python hiện riêng một dòng.
const CONDITIONAL_RELIC_IDS = new Set(['brace', 'repair', 'star', 'thread', 'cornerstone',
  'insurance', 'phoenix', 'spine', 'eternalseed']);

let rankCandidates = null;
const rankJob = { key: '', queue: [], result: null, campaign: null, valueAt: null };

function relicCandidates() {
  if (rankCandidates === null && itemTexts) {
    rankCandidates = Object.entries(itemTexts.items)
      .filter(([id, t]) => !NON_SHELF_IDS.has(id) && !CONDITIONAL_RELIC_IDS.has(id) &&
                           !NON_SHELF_TEXT.test((t && t.description) || ''))
      .map(([id]) => id);
  }
  return rankCandidates || [];
}

function startRankJob(key, campaign, roomObj, multiplier) {
  const relics = campaign.relics || [];
  const owned = relics.filter(r => r.id).map(r => r.id);
  const balance = roomObj.add(BALANCE_OFF).readPointer();
  const base = balance.isNull() ? 320 : balance.add(BALANCE_BASE_VALUE_OFF).readDouble();
  rankJob.key = key;
  rankJob.campaign = campaign;
  rankJob.valueAt = g => base * Math.pow(multiplier, g);
  rankJob.result = { baseline: {}, items: {}, owned: {}, shelfFull: !relics.some(r => !r.id) };
  rankJob.queue = [{ kind: 'baseline', relics }]
    .concat(owned.map(id => ({ kind: 'owned', id, relics: editRelics(relics, { removeId: id }) })))
    .concat(relicCandidates().filter(id => !owned.includes(id))
      .map(id => ({ kind: 'items', id, relics: editRelics(relics, { addId: id }) })));
}

function runRankTask(task) {
  const fake = fakeCampaign(rankJob.campaign, { relics: task.relics });
  const out = {};
  for (const g of RANK_GRADES) out[g] = oddsAtGrade(fake, g, rankJob.valueAt(g), false);
  if (task.kind === 'baseline') rankJob.result.baseline = out;
  else rankJob.result[task.kind][task.id] = out;
}

// Gọi mỗi lần Update (đã giới hạn tần suất): trả kết quả đúng MỘT lần khi vừa mô phỏng xong
// toàn bộ, còn lại null. Lỗi ở một relic chỉ bỏ relic đó, không làm dừng đọc trực tiếp.
function collectRelicRank(roomObj, multiplier) {
  const campaignObj = roomObj.add(CAMPAIGN_OFF).readPointer();
  if (campaignObj.isNull()) return null;
  const campaign = JSON.parse(readManagedString(invoke(toJson, NULL, [campaignObj])));
  const key = JSON.stringify(campaign.relics || []);
  if (key !== rankJob.key) startRankJob(key, campaign, roomObj, multiplier);
  if (!rankJob.queue.length) return null;
  for (let i = 0; i < RANK_BATCH && rankJob.queue.length; i++) {
    const task = rankJob.queue.shift();
    try {
      runRankTask(task);
    } catch (e) {
      if (task.kind === 'baseline') { rankJob.queue = []; return null; }  // không có mốc so sánh
    }
  }
  return rankJob.queue.length ? null : rankJob.result;
}
