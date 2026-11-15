# ForgeSeer

**Overlay chiến thuật cho game ForgeTax** – xem tỉ lệ thật của từng nhát búa, biết khi nào nên đập, khi nào nên dừng, nộp cống bằng kiếm nào và nên mua di vật gì.

> Công cụ không chính thức, không liên kết với nhà phát triển ForgeTax. ForgeSeer **chỉ đọc** dữ liệu: không sửa tỉ lệ, không sửa file save, không đoán trước kết quả nhát búa.

*English: ForgeSeer is an unofficial, read-only strategy overlay for the game ForgeTax (Windows). It shows the game's real next-strike odds, an optimal multi-strike plan, tribute/quota planning and relic advice. UI is in Vietnamese.*

## Tính năng

- **Tỉ lệ thật của nhát kế tiếp** cho từng thanh kiếm (Gãy · Hư tổn · Không đổi · Thành công · Xuất sắc), lấy từ chính hàm tính tỉ lệ của game – đã gồm hiệu ứng mọi di vật đang có.
- **Gợi ý ĐẬP / DỪNG**: kỳ vọng 1 nhát và **kế hoạch nhiều nhát** (quy hoạch động, có tính Xuất Thần – trong Xuất Thần kiếm không gãy). Số nhát Xuất Thần được hiệu chỉnh theo tay bạn.
- **Cống nạp**: cống hôm nay, lịch cống các ngày tới (tính bằng hàm của game), thước đo tiến độ, chọn kiếm nộp tối ưu (mất ít giá trị tương lai nhất).
- **Di vật**: mô phỏng mua / bỏ / đổi từng món, xếp hạng **di vật giảm tỉ lệ gãy** ở cấp +8/+12/+16, đánh dấu ★ món đáng săn khi đang bán.
- **Thương nhân ma**: chấm từng món (Kiếm Sắt, Vảy Rồng, Dây Cót…) theo giá trị so với giá.
- **Khung "Việc cần làm"** ở góc phải: từng bước nên làm ngay (Xuất Thần, nộp cống, đập kiếm nào, mua gì).
- Tên và mô tả di vật **tiếng Việt chính thức** của game; kiếm được gọi theo vị trí nhìn thấy (`+8 giá ô 2`, `+5 dưới sàn`, `trên đe`), kiếm trên đe luôn đứng đầu.
- Nhật ký lượt chơi và từng ngày để so sánh chiến thuật.

## Cài đặt & chạy

### Cách 1 – Bản đóng gói (khuyên dùng)
1. Tải `ForgeSeer-<phiên bản>-windows.zip` ở mục [Releases](../../releases), giải nén.
2. Mở ForgeTax ở chế độ **Windowed / Borderless** (overlay không hiện trên Exclusive Fullscreen).
3. Chạy `ForgeSeer.exe`.

### Cách 2 – Từ mã nguồn
```bash
pip install frida
python -m forgeseer            # mở overlay
python -m forgeseer --no-live  # chỉ đọc file save, không gắn vào game
python -m forgeseer --once     # in trạng thái ra console
```
Cần Python 3.10+ trên Windows.

## Phím tắt

| Phím | Tác dụng |
|---|---|
| F7 | Bật/tắt khung chú giải |
| F8 | Ẩn/hiện overlay |
| F9 | Kéo để di chuyển (bấm lại để khóa, vị trí được nhớ) |
| F10 | Thoát |

## Cách hoạt động

- **Đọc trực tiếp**: ForgeSeer dùng [Frida](https://frida.re) gắn vào `ForgeTax.exe`, gọi các hàm *chỉ đọc* của game trên main thread (chụp trạng thái, tính tỉ lệ) và gửi ra overlay ~0,3 giây/lần. Mô phỏng di vật dùng bản sao campaign mới, không đụng dữ liệu thật.
- **Dự phòng**: khi không gắn được (game chưa mở, tạm dừng…), overlay đọc file save trong `%USERPROFILE%\AppData\LocalLow\DefaultCompany\ForgeTax\Save`.
- Chi tiết kỹ thuật: [docs/forgeseer-handoff.md](docs/forgeseer-handoff.md).

## Lưu ý

- Phần mềm diệt virus có thể cảnh báo vì Frida gắn vào tiến trình khác. Mã nguồn mở để bạn tự kiểm tra hoặc tự build.
- Game có bảng xếp hạng trực tuyến. ForgeSeer không thay đổi kết quả, nhưng hãy tự cân nhắc việc dùng công cụ hỗ trợ.
- Bản cập nhật game có thể làm thay đổi cấu trúc dữ liệu; khi đó chế độ đọc trực tiếp có thể tạm ngừng cho tới khi ForgeSeer được cập nhật.

## Phát triển

```bash
pip install pytest frida
python -m pytest -q
```
Đẩy tag `v*` sẽ tự build `ForgeSeer.exe` và tạo bản phát hành trên GitHub.

## Giấy phép

[MIT](LICENSE)
