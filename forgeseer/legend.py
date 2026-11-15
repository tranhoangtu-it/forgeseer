"""Khung "Chú giải" (bật/tắt bằng F7): giải thích các thuật ngữ trên overlay."""
from __future__ import annotations

from .text_format import wrap_lines

TITLE, NORMAL, DIM = "title", "normal", "dim"
Line = tuple[str, str]

# (thuật ngữ, giải thích)
LEGEND_ENTRIES: tuple[tuple[str, str], ...] = (
    ("Gãy · Hư tổn · Không đổi · Thành công · Xuất sắc",
     "5 kết quả của một nhát rèn, theo thứ tự: mất kiếm; −1 cấp; giữ nguyên; +1 cấp; +2 cấp."),
    ("kỳ vọng ×1,21",
     "Giá trị kỳ vọng sau 1 nhát so với hiện tại. Trên ×1 là có lời, dưới ×1 là lỗ."),
    ("Kế hoạch nhiều nhát",
     "Kỳ vọng khi đập tiếp nhiều nhát và dừng đúng lúc (tính cả đợt Xuất Thần)."),
    ("Tiến độ",
     "Kiếm đang giữ + kiếm mới mỗi ngày (ước tính thận trọng) so với cống 3 ngày tới."),
    ("Xuất Thần & tích lực",
     "Đủ 10 điểm tích lực (10 nhát thường) thì vào Xuất Thần: vài giây đập không thể gãy. "
     "\"~7 nhát/lần\" = số nhát bạn thường đập kịp trong một đợt."),
    ("Cống hôm nay / ngày mai",
     "Giá trị kiếm phải nộp cuối ngày; ngày mai là mức game tính sẵn cho ngày kế tiếp."),
    ("Vị trí kiếm",
     "giá ô N = trên giá, ô thứ N; dưới sàn; trên đe; bàn cống = đã đặt lên bàn nộp; "
     "đang cầm = trên tay hoặc trong lò."),
    ("có thể bỏ / nên bỏ nhất",
     "Bỏ di vật đó không làm đổi tỉ lệ / làm kỳ vọng giảm ít nhất khi cần chỗ trống."),
    ("★", "Di vật đang bán nằm trong nhóm giảm tỉ lệ Gãy nhiều nhất."),
    ("an toàn", "Nhát này không thể Gãy (tỉ lệ Gãy 0%)."),
    ("Lượt mua di vật · Lượt đổi hàng",
     "Số lượt mua ở cửa hàng di vật (trả bằng kiếm +0); số lần đổi hàng của cửa hàng."),
    ("Vảy Rồng (Q) · Dây Cót (R)",
     "Vảy Rồng Nứt chặn Gãy ở nhát kế tiếp; Dây Cót Hối Tiếc hoàn tác nhát vừa rồi."),
)


def legend_lines() -> list[Line]:
    lines: list[Line] = [("Chú giải (F7 để tắt)", TITLE)]
    for term, meaning in LEGEND_ENTRIES:
        lines += [(term, NORMAL), (f"  {meaning}", DIM)]
    return wrap_lines(lines)
