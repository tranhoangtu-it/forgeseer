"""Cửa sổ trong suốt, luôn nằm trên, cho chuột bấm xuyên qua (Win32) dùng cho các khung overlay."""
from __future__ import annotations

import ctypes
import tkinter as tk
import tkinter.font as tkfont
from ctypes import wintypes

from .action_plan import ALERT
from .formatter import DIM, GOOD, NORMAL, TITLE, WARN
from .text_format import display_width

BG = "#101014"
COLORS = {TITLE: "#f0c060", NORMAL: "#e8e8e8", GOOD: "#7ee08a", WARN: "#ff6b5b", DIM: "#9a9aa8"}
FONT_FAMILY = "Consolas"
ALERT_EXTRA_POINTS = 4  # chữ cảnh báo to hơn chữ thường
ALERT_BG = "#b01818"

GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080  # ẩn khỏi taskbar / Alt+Tab

_user32 = ctypes.windll.user32
_user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
_user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
_user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
_user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
_user32.GetAsyncKeyState.restype = ctypes.c_short


def enable_dpi_awareness() -> None:
    """Chữ sắc nét trên màn hình scale >100%. Bỏ qua nếu Windows không hỗ trợ."""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass


def key_is_down(vk: int) -> bool:
    return bool(_user32.GetAsyncKeyState(vk) & 0x8000)


class OverlayFonts:
    """Font dùng chung cho mọi khung; đổi cỡ một chỗ là mọi khung đổi theo."""

    def __init__(self, master: tk.Misc, size: int) -> None:
        self.normal = tkfont.Font(master, family=FONT_FAMILY, size=size)
        self.bold = tkfont.Font(master, family=FONT_FAMILY, size=size, weight="bold")
        self.alert = tkfont.Font(master, family=FONT_FAMILY, size=size + ALERT_EXTRA_POINTS,
                                 weight="bold")

    def resize(self, size: int) -> None:
        self.normal.configure(size=size)
        self.bold.configure(size=size)
        self.alert.configure(size=size + ALERT_EXTRA_POINTS)


class OverlayWindow:
    """Một khung overlay: Toplevel không viền + ô chữ, mặc định cho chuột bấm xuyên qua."""

    def __init__(self, master: tk.Misc, fonts: OverlayFonts, alpha: float) -> None:
        self.alpha = alpha
        self.window = tk.Toplevel(master)
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", True)
        self.window.attributes("-alpha", alpha)
        self.window.configure(bg=BG)
        self.text = _make_text(self.window, fonts)
        self.window.update_idletasks()
        self.hwnd = _user32.GetParent(self.window.winfo_id()) or self.window.winfo_id()
        self.set_click_through(True)

    def set_click_through(self, enabled: bool) -> None:
        style = _user32.GetWindowLongPtrW(self.hwnd, GWL_EXSTYLE)
        style |= WS_EX_LAYERED | WS_EX_TOOLWINDOW
        style = style | WS_EX_TRANSPARENT if enabled else style & ~WS_EX_TRANSPARENT
        _user32.SetWindowLongPtrW(self.hwnd, GWL_EXSTYLE, style)
        # Tk tự đặt lại alpha khi đổi style layered -> gán lại cho chắc.
        self.window.attributes("-alpha", self.alpha)

    def set_alpha(self, alpha: float) -> None:
        self.alpha = alpha
        self.window.attributes("-alpha", alpha)

    def show(self, shown: bool) -> None:
        if shown:
            self.window.deiconify()
        else:
            self.window.withdraw()

    def fill(self, lines: list[tuple[str, str]]) -> None:
        fill_text(self.text, lines)

    def move(self, x: int, y: int) -> None:
        self.window.geometry(f"+{x}+{y}")


def _make_text(parent: tk.Misc, fonts: OverlayFonts) -> tk.Text:
    text = tk.Text(parent, bg=BG, bd=0, highlightthickness=0, font=fonts.normal,
                   padx=10, pady=8, wrap="none", cursor="arrow")
    for tag, color in COLORS.items():
        text.tag_configure(tag, foreground=color)
    text.tag_configure(TITLE, foreground=COLORS[TITLE], font=fonts.bold)
    text.tag_configure(ALERT, foreground="#ffffff", background=ALERT_BG, font=fonts.alert)
    text.pack()
    return text


def fill_text(widget: tk.Text, lines: list[tuple[str, str]]) -> None:
    widget.configure(state="normal")
    widget.delete("1.0", "end")
    for text, tag in lines:
        widget.insert("end", text + "\n", tag)
    widget.delete("end-2c", "end-1c")  # bỏ dòng trống cuối
    width = max(display_width(text) for text, _ in lines)
    widget.configure(state="disabled", width=width + 1, height=len(lines))
