# ForgeTax Overlay – tài liệu bàn giao

Overlay (Python + tkinter, Windows) hiển thị trạng thái lượt chơi ForgeTax và gợi ý chiến thuật.
Chạy: `cd E:\tool-game && pythonw -m forgetax_overlay` (`--no-live` chỉ đọc file save, `--once` in console).
Test: `python -m pytest -q` (pytest, `pyproject.toml` đặt `pythonpath=["."]`).
Phím: F8 ẩn/hiện, F9 kéo/khóa vị trí (lưu `%APPDATA%\ForgeTaxOverlay\config.json`), F10 thoát.
Khởi động lại sau khi sửa: dừng tiến trình `pythonw` đang chạy overlay rồi chạy lại lệnh trên.

## Nguyên tắc
- **Chỉ đọc**: không ghi field nào của game, không ghi file save. Mô phỏng dùng object MỚI tạo bằng `JsonUtility.FromJson`.
- Không làm tính năng đoán trước kết quả từ trạng thái RNG (`random.s0..s3` trong save) – game có bảng xếp hạng.
- Mọi lời khuyên dựa trên xác suất do chính hàm của game tính.

## Kiến trúc (`forgetax_overlay/`)
| File | Vai trò |
|---|---|
| `save_reader.py` | Parse JSON save → `RunState`, `Sword`, `Relic`, `Offer`, `MerchantOffer`. `Sword.tag` = "+N vị trí". |
| `live_capture.js` | Script Frida chạy trong game (hook `GPT6ForgeRoom.Update`, main thread) gửi JSON trạng thái + tỉ lệ + mô phỏng. |
| `live_source.py` | Luồng nền gắn Frida vào `ForgeTax.exe`, nhận message, cache tên relic. |
| `advisor.py` | `SwordOdds`, EV 1 nhát, `ShopSimulation`, `GradeOddsTable`. |
| `planner.py` | DP dừng tối ưu theo (grade, tích lực), có đợt Xuất Thần. |
| `tribute.py` | Tình trạng cống, gợi ý ưu tiên đủ cống. |
| `sword_section.py` | Hiển thị kiếm + `sword_verdict` (thứ tự ưu tiên: Xuất Thần > cống > kế hoạch > EV). |
| `shop_advice.py` | Gợi ý mua/bỏ/đổi relic (mô phỏng). |
| `merchant_advice.py` | Gợi ý mua hàng Thương nhân ma. |
| `action_plan.py` | Khung "Việc cần làm" (góc phải). |
| `formatter.py` | Khung chi tiết (góc trái). |
| `overlay.py` | Hai cửa sổ tkinter trong suốt, click-through (WS_EX_TRANSPARENT). |
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
  Các mã khác (trên tay / trong lò) chưa phân biệt.
- Thương nhân ma: `campaign.merchantOffers[{id, price, sold, grade, stock, purchases}]`, có mặt khi
  `merchantRound == round`. id đã gặp: `sword`, `worldtree`, `ward` (Vảy Rồng Nứt), `rewind` (Dây Cót Hối Tiếc).

## Giả định chưa xác minh chắc
- Xuất Thần: 10 nhát thường thì nhát kế vào Xuất Thần, kéo dài ~4 giây. Planner giả định `FEVER_STRIKES=4`;
  hướng dẫn cộng đồng (grindnstrat.com) nói ~7 nhát khi đập hết tốc.
- Hư tổn = -1 grade, Xuất sắc = +2, giá trị mỗi grade × gradeMultiplier.
- Theo hướng dẫn cộng đồng: lỡ cống lần 3 là thua; kiếm nộp cống đổi lại thành vàng; máy relic tính 1 credit/kiếm
  (trả bằng kiếm +0); Royal Change: 30% phần nộp dư trừ vào cống lần sau (tối đa -30%).

## Lưu ý môi trường
- Hook "Fact-Forcing Gate" chặn lần ghi/sửa đầu mỗi file: trình bày thông tin (ai gọi file, dữ liệu, yêu cầu) rồi thử lại.
- Dò game bằng script Frida tạm (đặt ngoài repo); chỉ gọi hàm thuần/getter trên main thread (trong hook `Update`).
