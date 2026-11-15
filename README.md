<div align="center">

# 🔮 ForgeSeer

### Nhìn thấu từng nhát búa trong **ForgeTax**
*See through every hammer strike in ForgeTax*

[![Release](https://img.shields.io/github/v/release/tranhoangtu-it/forgeseer?style=for-the-badge&color=f0a030)](https://github.com/tranhoangtu-it/forgeseer/releases/latest)
[![Downloads](https://img.shields.io/github/downloads/tranhoangtu-it/forgeseer/total?style=for-the-badge&color=7ee08a)](https://github.com/tranhoangtu-it/forgeseer/releases)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue?style=for-the-badge)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows-0078D6?style=for-the-badge&logo=windows)](#-cài-đặt)
[![Python](https://img.shields.io/badge/python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](#-chạy-từ-mã-nguồn)
[![Stars](https://img.shields.io/github/stars/tranhoangtu-it/forgeseer?style=for-the-badge&color=yellow)](https://github.com/tranhoangtu-it/forgeseer/stargazers)

**[⬇️ Tải bản mới nhất](https://github.com/tranhoangtu-it/forgeseer/releases/latest)** · [Tính năng](#-tính-năng) · [Cài đặt](#-cài-đặt) · [English](#-english) · [Báo lỗi](https://github.com/tranhoangtu-it/forgeseer/issues/new/choose)

<img src="docs/images/forgeseer-overlay.png" alt="ForgeSeer overlay trong ForgeTax" width="820">

</div>

---

Bạn cứ gãy kiếm ở +14? Không biết nên nộp cống thanh nào? **ForgeSeer** là overlay đặt ngay trên màn hình game, đọc **tỉ lệ thật** từ chính game và nói cho bạn biết **nên làm gì tiếp theo**.

> 🛡️ **Chỉ đọc – công bằng:** không sửa tỉ lệ, không sửa file save, không đoán trước kết quả. Công cụ không chính thức, không liên kết với nhà phát triển ForgeTax.

## ✨ Tính năng

| | Tính năng | Bạn nhận được |
|---|---|---|
| 🎯 | **Tỉ lệ thật từng nhát** | Gãy · Hư tổn · Không đổi · Thành công · Xuất sắc – tính bằng chính hàm của game, đã gồm mọi di vật |
| ⚒️ | **ĐẬP hay DỪNG** | Kỳ vọng 1 nhát + **kế hoạch nhiều nhát** (quy hoạch động, tính cả Xuất Thần) |
| 🔥 | **Xuất Thần theo tay bạn** | Đo số nhát bạn thật sự đập được mỗi lần Xuất Thần, cảnh báo nổi bật khi đang Xuất Thần |
| 🐉 | **Cống nạp & tiến độ** | Cống hôm nay, lịch cống các ngày tới, "đủ cho N ngày" hay "chậm X", chọn kiếm nộp tối ưu |
| 💎 | **Di vật** | Mô phỏng mua / bỏ / đổi từng món, **bảng di vật giảm tỉ lệ gãy** ở +8/+12/+16, ★ món đáng săn |
| 👻 | **Thương nhân ma** | Chấm Kiếm Sắt, Vảy Rồng, Dây Cót… theo giá trị so với giá |
| 📋 | **Việc cần làm** | Khung bên phải: từng bước nên làm ngay, theo thứ tự ưu tiên |
| 🇻🇳 | **Tiếng Việt chuẩn game** | Tên & mô tả di vật chính thức; kiếm gọi theo vị trí (`+8 giá ô 2`, `trên đe`) – kiếm trên đe luôn đứng đầu |
| 📖 | **Chú giải (F7)** | Giải thích mọi khái niệm ngay trong game |
| 📈 | **Nhật ký** | Ghi lại từng lượt chơi và từng ngày để so sánh chiến thuật |

## 📦 Cài đặt

1. Tải **`ForgeSeer-<phiên bản>-windows.zip`** ở [Releases](https://github.com/tranhoangtu-it/forgeseer/releases/latest) và giải nén.
2. Mở ForgeTax ở chế độ **Windowed / Borderless** *(overlay không hiện trên Exclusive Fullscreen)*.
3. Chạy **`ForgeSeer.exe`** – overlay tự gắn vào game, vào chơi là thấy.

### ⌨️ Phím tắt

| Phím | Tác dụng |
|:---:|---|
| `F7` | Bật/tắt khung chú giải |
| `F8` | Ẩn/hiện overlay |
| `F9` | Kéo để di chuyển (bấm lại để khóa – vị trí được nhớ) |
| `F10` | Thoát |

### 🐍 Chạy từ mã nguồn

```bash
pip install frida
python -m forgeseer            # mở overlay
python -m forgeseer --no-live  # chỉ đọc file save
python -m forgeseer --once     # in trạng thái ra console
```

## 💡 Mẹo đi xa hơn (rút ra từ dữ liệu game)

- Đập kiếm cấp cao **trong Xuất Thần** – khi đó kiếm không thể gãy.
- Săn **Liềm Và Búa** và **Kìm Vảy Rồng** sớm – hai di vật giảm tỉ lệ gãy mạnh nhất.
- Đừng nộp cống bằng kiếm còn tiềm năng; cống tăng ~1,4–1,5×/ngày, bạn cần vài thanh rất cao.
- Để dành **Vảy Rồng (Q)** cho nhát rủi ro trên thanh quý nhất, **Dây Cót (R)** để hồi khi nó gãy.

## ⚙️ Cách hoạt động

- **Đọc trực tiếp:** dùng [Frida](https://frida.re) gắn vào `ForgeTax.exe`, gọi các hàm *chỉ đọc* của game trên main thread (chụp trạng thái, tính tỉ lệ) ~0,3 giây/lần. Mô phỏng di vật chạy trên **bản sao** campaign, không đụng dữ liệu thật.
- **Dự phòng:** không gắn được thì đọc file save của game.
- Chi tiết kỹ thuật: [docs/forgeseer-handoff.md](docs/forgeseer-handoff.md).

## ⚠️ Lưu ý

- Phần mềm diệt virus có thể cảnh báo vì Frida gắn vào tiến trình khác – mã nguồn mở để bạn tự kiểm tra hoặc tự build.
- Game có bảng xếp hạng trực tuyến; ForgeSeer không thay đổi kết quả, nhưng hãy tự cân nhắc việc dùng công cụ hỗ trợ.
- Bản cập nhật game có thể làm chế độ đọc trực tiếp tạm ngừng cho tới khi ForgeSeer được cập nhật.

## 🌍 English

**ForgeSeer** is an unofficial, **read-only** strategy overlay for the roguelite **ForgeTax** (Windows, Steam).

- 🎯 **Real next-strike odds** for every sword, computed by the game's own odds function (all relic effects included).
- ⚒️ **Strike or stop** advice: one-strike expected value plus an **optimal multi-strike plan** (dynamic programming, Frenzy-aware, calibrated to your own Frenzy speed).
- 🐉 **Tribute planning**: today's quota, the upcoming quota schedule, a pace meter, and an optimal choice of swords to offer.
- 💎 **Relic advisor**: simulated buy / drop / swap, a **break-reduction ranking** at +8/+12/+16, ghost-merchant value checks.
- 📋 An **action panel** listing exactly what to do next.

It attaches with Frida and only calls the game's read-only functions on simulated copies — it never changes odds, saves or outcomes, and never predicts RNG. The UI is in Vietnamese (official in-game Vietnamese terms). Download from [Releases](https://github.com/tranhoangtu-it/forgeseer/releases/latest), run ForgeTax windowed/borderless, then launch `ForgeSeer.exe`.

## 🤝 Đóng góp

Mọi góp ý, báo lỗi, ý tưởng đều được chào đón – xem [CONTRIBUTING.md](CONTRIBUTING.md) và [CHANGELOG.md](CHANGELOG.md).
Nếu ForgeSeer giúp bạn đi xa hơn, hãy để lại một ⭐ cho repo!

## 📄 Giấy phép

[MIT](LICENSE)
