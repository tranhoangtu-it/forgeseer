# Đóng góp cho ForgeSeer

Cảm ơn bạn đã quan tâm! Mọi đóng góp đều được chào đón.

## Báo lỗi / đề xuất
- Dùng [mẫu báo lỗi hoặc đề xuất](https://github.com/tranhoangtu-it/forgeseer/issues/new/choose).
- Ghi rõ phiên bản ForgeSeer, ngày trong game, và ảnh chụp overlay nếu có.

## Phát triển
```bash
pip install pytest frida
python -m pytest -q
python -m forgeseer
```
- Đọc [docs/forgeseer-handoff.md](docs/forgeseer-handoff.md) trước: kiến trúc và các dữ kiện game đã xác minh.
- Viết test trước cho logic thuần (pytest), giữ module gọn.
- Commit theo [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `docs:`…).

## Nguyên tắc bắt buộc
- **Chỉ đọc**: không ghi dữ liệu game hay file save; mô phỏng chỉ trên bản sao tạo mới.
- **Không** dự đoán kết quả từ trạng thái RNG của game.
- Chữ trên giao diện: tiếng Việt theo thuật ngữ chính thức của game, không viết tắt.
