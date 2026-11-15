"""Khung "Chú giải" (bật/tắt bằng F7): giải thích các thuật ngữ trên overlay."""
from __future__ import annotations

from .i18n import t
from .text_format import wrap_lines

TITLE, NORMAL, DIM = "title", "normal", "dim"
Line = tuple[str, str]

# Mỗi mục là cặp khóa catalog ``legend.<tên>.term`` / ``legend.<tên>.meaning``.
LEGEND_KEYS: tuple[str, ...] = (
    "outcomes", "ev", "plan", "pace", "fever", "tribute", "place", "drop", "star", "safe",
    "credits", "consumables",
)


def legend_lines() -> list[Line]:
    lines: list[Line] = [(t("legend.title"), TITLE)]
    for key in LEGEND_KEYS:
        lines += [(t(f"legend.{key}.term"), NORMAL), ("  " + t(f"legend.{key}.meaning"), DIM)]
    return wrap_lines(lines)
