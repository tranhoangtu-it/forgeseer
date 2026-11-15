# ForgeTax Overlay – tài liệu bàn giao

Overlay (Python + tkinter, Windows) hiển thị trạng thái lượt chơi ForgeTax và gợi ý chiến thuật.
Chạy: `cd E:\tool-game && pythonw -m forgetax_overlay` (`--no-live` chỉ đọc file save, `--once` in console).
Test: `python -m pytest -q` (pytest, `pyproject.toml` đặt `pythonpath=["."]`).
Phím: F7 bật/tắt khung "Chú giải", F8 ẩn/hiện, F9 kéo/khóa vị trí (lưu `%APPDATA%\ForgeTaxOverlay\config.json`), F10 thoát.
Khởi động lại sau khi sửa: dừng tiến trình `pythonw` đang chạy overlay rồi chạy lại lệnh trên.

## Nguyên tắc
- **Chỉ đọc**: không ghi field nào của game, không ghi file save. Mô phỏng dùng object MỚI tạo bằng `JsonUtility.FromJson`.
- Không làm tính năng đoán trước kết quả từ trạng thái RNG (`random.s0..s3` trong save) – game có bảng xếp hạng.
- Mọi lời khuyên dựa trên xác suất do chính hàm của game tính.
- Chữ trên UI: tiếng Việt, không viết tắt, dùng thuật ngữ chính thức của game (bảng ngôn ngữ `vi`):
  Gãy / Hư tổn / Không đổi / Thành công / Xuất sắc, cấp (+N), di vật, cửa hàng di vật, đổi hàng,
  lượt mua (ở cửa hàng di vật), Vảy Rồng (Nứt), Dây Cót (Hối Tiếc), Xuất Thần, tích lực.
  Số qua `text_format` (`fmt_int` 44.200, `fmt_ratio` ×1,21, `fmt_pct` 19%); "→" thay "->",
  " · " ngăn ý; dòng > `LINE_WIDTH` (72) tự tách thành dòng phụ thụt vào (`wrap_lines`);
  khung trái cách phần bằng dòng trống; khung phải mỗi bước một dòng, chi tiết ở dòng phụ.
  Thuật ngữ mới trên UI -> thêm giải thích vào `legend.py`.

## Kiến trúc (`forgetax_overlay/`)
| File | Vai trò |
|---|---|
| `save_reader.py` | Parse JSON save → `RunState`, `Sword`, `Relic`, `Offer`, `MerchantOffer`. `Sword.tag` = "+N vị trí". |
| `live_capture.js` | Script Frida chạy trong game (hook `GPT6ForgeRoom.Update`, main thread) gửi JSON trạng thái + tỉ lệ + mô phỏng. |
| `live_source.py` | Luồng nền gắn Frida vào `ForgeTax.exe`, nhận message, cache tên relic. |
| `advisor.py` | `SwordOdds`, EV 1 nhát, `ShopSimulation`, `GradeOddsTable`. |
| `planner.py` | DP dừng tối ưu theo (grade, tích lực), có đợt Xuất Thần (`fever_strikes` nhát). `safe_only=True` = chỉ đập nhát không thể gãy (ước lượng thận trọng cho tiến độ). |
| `fever_calibration.py` | Đo số nhát/đợt Xuất Thần của người chơi, trung bình lưu ở config.json khóa `fever` (mặc định 7). |
| `reroll_advice.py` | Gợi ý đổi lượt máy relic (miễn phí / vàng dư ≥10× giá). |
| `run_log.py` | Ghi `%APPDATA%\ForgeTaxOverlay\runs.jsonl` khi lượt kết thúc (dedupe theo anonymousRunId) + dòng tóm tắt. |
| `config.py` | config.json dùng chung (vị trí `x/y`, `fever`); ghi = gộp khóa. |
| `tribute.py` | Tình trạng cống, gợi ý ưu tiên đủ cống; `choose_tribute` = duyệt mọi tập con (n ≤ 12, nhiều hơn thì tham lam) chọn kiếm nộp đủ cống mà mất ít giá trị tương lai nhất (giá trị × `Plan.ratio`, kiếm đã xong = 1; hòa -> nộp dư ít nhất). |
| `pace.py` | Tiến độ khế ước: ước tính kiếm đang giữ (giá trị × kỳ vọng nhát an toàn) + 3 kiếm +0/ngày so với cống cộng dồn 3 ngày tới -> "Tiến độ: đủ cho N ngày tới" / "Chậm: thiếu X". `risk_hint`: chậm -> đẩy kiếm chính (Xuất Thần / Vảy Rồng), dư ≥1.5× -> đừng mạo hiểm nhát gãy ≥10%; không bao giờ đè kiếm giữ cho cống HÔM NAY. Dòng "Cống sắp tới". |
| `day_log.py` | Ghi `%APPDATA%\ForgeTaxOverlay\days.jsonl`: bản chụp cuối mỗi ngày (round, quota, delivered, holdings, top_grade, missed) khi round đổi / lượt kết thúc; dedupe theo (run_id, round). Chưa hiển thị trên UI. |
| `sword_section.py` | Hiển thị kiếm + `sword_verdict` (thứ tự ưu tiên: Xuất Thần > cống > kế hoạch > EV). |
| `shop_advice.py` | Gợi ý mua/bỏ/đổi relic (mô phỏng). |
| `merchant_advice.py` | Gợi ý mua hàng Thương nhân ma. |
| `action_plan.py` | Khung "Việc cần làm" (góc phải). |
| `formatter.py` | Khung chi tiết (góc trái). |
| `text_format.py` | Định dạng số kiểu Việt + tách dòng dài, dùng chung cho mọi khung. |
| `legend.py` | Nội dung khung "Chú giải" (F7). |
| `overlay.py` | Ba cửa sổ tkinter trong suốt, click-through (WS_EX_TRANSPARENT): chi tiết, "Việc cần làm", "Chú giải" (ẩn tới khi bấm F7). |
| `live_quota_schedule.js` | Nối sau `live_relic_rank.js`. `forecastSchedule` gửi `quotaSchedule` = cống từng ngày round+1..min(contractDeadlineRound, round+10) (`nextQuota` = phần tử đầu). |
| `live_relic_rank.js` | Nối SAU `live_capture.js` thành một script (`live_source.load_script_source`), dùng chung helper. Xếp hạng relic theo mức giảm gãy. |
| `relic_rank.py` | Parse `relicRank`, xếp hạng (top 8 theo giảm gãy @+12, hòa -> +16 -> +8), khung "Relic giảm gãy", bước "★ Mua". |
| `relic_names.py/.json` | Tên tự dịch (dự phòng); tên chính thức từ game cache ở `%APPDATA%\ForgeTaxOverlay\relic_texts.json`. |

## Dữ liệu game đã dò được (Unity 6000.5 IL2CPP + Obfuz – tên hàm bị làm rối, tên field serialize còn nguyên)
- Save: `%USERPROFILE%\AppData\LocalLow\DefaultCompany\ForgeTax\Save\run_release*_v*.json`
  dạng `{version, payload: "<JSON>", checksum}`. Payload = `ForgeSavedRun` (campaign, swords, delivered, ...).
- `GameAssembly.dll` export đủ `il2cpp_*` → Frida gọi được runtime.
- `GPT6ForgeRoom` (MonoBehaviour): field `campaign` (ForgeCampaign), `quota` (cống phải nộp vòng này),
  `enhancementBalance` (ScriptableObject: `baseValue`=320, `gradeMultiplier`@32 float =1.5, `rows` bảng tỉ lệ gốc),
  list `GPT6Sword` ở các field `$UB/$ic/$rc` (tìm theo kiểu, trừ `swordPrefab`).
  Hàm instance 0 tham số trả `ForgeSavedRun` (hiện là `$KC`) = chụp trạng thái để save → `JsonUtility.ToJson`.
- `GPT6Sword` offset: serial@36, strikes@40, value@72 (double), grade@80, effects@96, heated@104, broken@105.
  `ForgeSwordEffects`: charge@244 (tích lực), normalHits@248, feverUntil@236 (float, theo thời gian), feverDuration@324.
- Tỉ lệ: `$xA::$PH(GPT6Sword, ForgeCampaign, bool fever)` → struct 5 int phần nghìn
  [gãy, hỏng, giữ, thành công, xuất sắc]. `$xA::$pH(int grade, ForgeCampaign, double value, bool fever)` = theo grade
  (script tự kiểm khớp với `$PH`; giai đoạn mở đầu game trả tỉ lệ cố định).
- Bảng ngôn ngữ: field tĩnh `Dictionary<lang, Dictionary<key,text>>` của `ForgeLocalization`; có `vi` (902 mục).
  Relic: `item.<id>.name/.description`. Duyệt Dictionary: mảng entries (Entry 24 byte: hash,next,key@8,value@16).
- Vị trí kiếm (`place`): 0 sàn, 3 trên đe, 4 giá (ô = `rack`+1), 5 bàn cống nạp (đã nộp → không tính là còn trong tay).
  Các mã khác (trên tay / trong lò) chưa phân biệt. Quan sát 4 phút: mã 1 (thường kèm con trỏ ở field
  `GPT6ForgeRoom.$oc`, khả năng là đang cầm) và mã 2 (ngắn, ~1 giây); chưa thấy `heated=true` nên chưa
  xác minh lò/tay -> overlay vẫn hiện "đang cầm" cho mã khác 0/3/4/5. `place` không phải field của
  GPT6Sword (chỉ có trong ForgeSavedSword khi chụp).
- Thương nhân ma: `campaign.merchantOffers[{id, price, sold, grade, stock, purchases}]`, có mặt khi
  `merchantRound == round`. id đã gặp: `sword`, `worldtree`, `ward` (Vảy Rồng Nứt), `rewind` (Dây Cót Hối Tiếc).
- Khế ước 24 ngày (`contractDeadlineRound`=24). `campaign.anonymousRunId` = định danh lượt (chuỗi hex 32 ký tự).
- Cống nạp: `ForgeCampaign.$gf()` = cống gốc theo `round`, `$Gf()` = cống thực phải nộp (đã trừ
  `tributeCredit`, Khế Ước Trọn Đời −30%; `contractInk` KHÔNG làm đổi). Đã kiểm: `$Gf` của campaign giả lập
  hôm nay == `GPT6ForgeRoom.quota`. Đường cống (balanceRevision 2): N1 1800, N2 2100, N3 2600, N4 3350,
  N5 4350, N6 5700, N7 8700, N8 13200, N9 20100, N10 29500, N12 65500, N14 140000, N16 290000, N18 534000,
  N20 824000, N22 1280000, N24 2000000 (khác số liệu cộng đồng cũ). `$ef()` = 0.15 × cống = giá đổi lượt
  máy relic (N7: 1,305 G khớp chữ trên máy), `$pf()` = 1.5×, `$Pf()` = 2×. `nextTributeCredit` = giảm cho
  lần cống sau (thông báo `notice.quota_credit`). Overlay gọi `$Gf` trên campaign giả lập round+1,
  tributeCredit = nextTributeCredit; các ngày sau tributeCredit = 0 (phần nộp dư tương lai chưa biết
  -> là mức trần). Đã chạy thật (ngày 7): `quotaSchedule` = 13200, 20100, 29500, 44200, 65500, 96400,
  140000, 204000, 290000, 413000 – khớp đường cống ở trên.
- `ForgeEnhancementBalance`: baseValue@24=320, gradeMultiplier@32=1.5, maxGrade@36=299, openingQuota@40=1800.
- Máy relic `GPT6ForgeRoom.vending` (ForgeRelicVending): TextMesh `rerollText` hiện "1,305 G" hoặc
  "1 LẦN MIỄN PHÍ" (`rework.free_reroll`); đọc bằng `TextMesh.get_text`. Campaign có `rerolls`,
  `paidRerolls`, `freeRerollUsedRound`.
- `GPT6ForgeRoom.ledgerText` (TextMesh) = "CỐNG PHẨM PHẢI NỘP\n2,600 G\n\nĐÃ CỐNG NẠP\n0 G".
- Xuất Thần (đo trực tiếp 2 lần): nhát thường thứ 10 kích hoạt, `feverRemaining` bắt đầu ~4.0 giây và giảm
  dần; trong 4 giây người chơi đập được 6 nhát (11..16). Overlay không tính nhát kích hoạt.
- Bàn Thờ Hai Mặt (`altar`): campaign có `forcedResultSerial`, `forcedNextResult` (=-1 khi không ấn định).
  `ForgeCampaign.$UE(id, GPT6Sword, balance, bool)` trả mô tả động của relic nhưng với kiếm null trả
  "Chưa thể dùng lúc này." -> chưa xác định được mặt hôm nay.

- Xếp hạng relic giảm gãy (payload `relicRank`, chỉ gửi khi bộ relic đổi và đã mô phỏng xong):
  `{baseline:{"8"|"12"|"16":[5 phần nghìn]}, items:{id:{grade:[5]}}, owned:{id:{grade:[5]}}, shelfFull}`.
  `items` = campaign giả lập + relic chưa có (kệ đầy vẫn thêm = ước lượng, overlay ghi "kệ đầy");
  `owned` = campaign giả lập BỎ relic đang có; `baseline` = campaign giả lập không đổi. Mọi số do
  `$pH(grade, fake, baseValue×hệ số^grade, false)`. Khóa cache = JSON `relics` (đổi phiếu vĩnh viễn
  bằng Dao Gọt Số Mệnh/phiếu mà relic giữ nguyên -> chưa tính lại). Chạy 12 campaign giả lập mỗi lần
  Update; đã chạy thật: 84 ứng viên, xong ~2 giây, không lỗi.
  Ứng viên = mọi `item.<id>` trong bảng ngôn ngữ, TRỪ: `ward, rewind, sword, worldtree` (hàng Thương
  nhân ma), đồ dùng ngay/tiêu hao `knife, starshard, powder, candle, chalk, oil, steelcore, echodust,
  oblivion, contractink, delivery, creditshelf`, phiếu `ticketdamage/hold/success/great`, món ngừng bán
  `ledger, safe`, mô tả chứa "Dùng ngay"/"không chiếm ô di vật"/"Tạm ngừng cung cấp", và relic có điều
  kiện `brace, repair, star, thread, cornerstone, insurance, phoenix, spine, eternalseed` (hiện ở dòng
  "Có điều kiện (không mô phỏng được)"). Lưu ý: `mold` và `thread` cùng tên "Chặn Giấy Nặng" trong bảng ngôn ngữ.

## Giả định chưa xác minh chắc
- Tiến độ: mỗi ngày nhận 3 kiếm +0 mới (`pace.FRESH_SWORDS_PER_DAY`, giá trị 320). Ước tính dùng kỳ
  vọng khi chỉ đập nhát không thể gãy vì với bảng tỉ lệ thật: kỳ vọng kế hoạch tối ưu của kiếm +0
  ≈ x81 (+3 x14.6, +6 x2.5) do ca hiếm lên rất cao, còn trung vị = 0 -> cả hai đều vô dụng để đo
  tiến độ. Ước tính hiện tại thận trọng (dễ báo "Chậm").
- Lịch cống các ngày sau ngày mai có thể giảm nhờ nộp dư (tributeCredit) – overlay hiện mức trần.
- Planner coi một đợt Xuất Thần = `fever_strikes` nhát tỉ lệ Xuất Thần ngay sau 10 nhát thường
  (số nhát hiệu chỉnh theo người chơi; mặc định 7 theo hướng dẫn cộng đồng khi chưa có mẫu).
- Gợi ý đổi lượt: ngưỡng "vàng dư" = ví ≥ 10 × giá (heuristic, vàng còn dùng cho Thương nhân ma).
- Hư tổn = -1 grade, Xuất sắc = +2, giá trị mỗi grade × gradeMultiplier.
- Theo hướng dẫn cộng đồng: lỡ cống lần 3 là thua; kiếm nộp cống đổi lại thành vàng; máy relic tính 1 credit/kiếm
  (trả bằng kiếm +0); Royal Change: 30% phần nộp dư trừ vào cống lần sau (tối đa -30%).

## Lưu ý môi trường
- Hook "Fact-Forcing Gate" chặn lần ghi/sửa đầu mỗi file: trình bày thông tin (ai gọi file, dữ liệu, yêu cầu) rồi thử lại.
- Dò game bằng script Frida tạm (đặt ngoài repo); chỉ gọi hàm thuần/getter trên main thread (trong hook `Update`).
  Hàm campaign chưa chắc thuần thì gọi trên campaign GIẢ LẬP (`JsonUtility.FromJson`), không gọi trên campaign thật.
