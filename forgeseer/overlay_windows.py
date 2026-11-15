"""Cửa sổ trong suốt, luôn nằm trên, cho chuột bấm xuyên qua (Win32) dùng cho các khung overlay."""
from __future__ import annotations

import ctypes
import os
import tkinter as tk
import tkinter.font as tkfont
from ctypes import wintypes

from .action_plan import ALERT
from .formatter import DIM, GOOD, NORMAL, TITLE, WARN
from .panel_layout import COLUMN_GAP, FontMetrics, Layout
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
MONITOR_DEFAULTTONEAREST = 2
# Thử bố cục trên màn hình nhỏ hơn: FORGESEER_WORK_AREA=1920x1040 (vùng làm việc giả, px).
WORK_AREA_ENV = "FORGESEER_WORK_AREA"

Area = tuple[int, int, int, int]  # left, top, right, bottom (px)


class _MonitorInfo(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]


_user32 = ctypes.windll.user32
_user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
_user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
_user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
_user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
_user32.GetAsyncKeyState.restype = ctypes.c_short
_user32.MonitorFromWindow.restype = wintypes.HMONITOR
_user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
_user32.GetMonitorInfoW.restype = wintypes.BOOL
_user32.GetMonitorInfoW.argtypes = [wintypes.HMONITOR, ctypes.POINTER(_MonitorInfo)]


def enable_dpi_awareness() -> None:
    """Chữ sắc nét trên màn hình scale >100%. Bỏ qua nếu Windows không hỗ trợ."""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass


def key_is_down(vk: int) -> bool:
    return bool(_user32.GetAsyncKeyState(vk) & 0x8000)


def measure_metrics(master: tk.Misc, sizes: range) -> dict[int, FontMetrics]:
    """Đo chiều cao dòng và bề rộng một cột của font overlay ở từng cỡ (theo DPI hiện tại)."""
    metrics = {}
    for size in sizes:
        font = tkfont.Font(master, family=FONT_FAMILY, size=size)
        metrics[size] = FontMetrics(font.metrics("linespace"), font.measure("0"))
    return metrics


class OverlayFonts:
    """Font của một khung; mỗi khung tự co cỡ chữ cho vừa màn hình nên không dùng chung."""

    def __init__(self, master: tk.Misc, size: int) -> None:
        self.size = size
        self.normal = tkfont.Font(master, family=FONT_FAMILY, size=size)
        self.bold = tkfont.Font(master, family=FONT_FAMILY, size=size, weight="bold")
        self.alert = tkfont.Font(master, family=FONT_FAMILY, size=size + ALERT_EXTRA_POINTS,
                                 weight="bold")

    def resize(self, size: int) -> None:
        if size == self.size:
            return
        self.size = size
        self.normal.configure(size=size)
        self.bold.configure(size=size)
        self.alert.configure(size=size + ALERT_EXTRA_POINTS)


class OverlayWindow:
    """Một khung overlay: Toplevel không viền + ô chữ, mặc định cho chuột bấm xuyên qua."""

    def __init__(self, master: tk.Misc, font_size: int, alpha: float) -> None:
        self.alpha = alpha
        self.fonts = OverlayFonts(master, font_size)
        self.window = tk.Toplevel(master)
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", True)
        self.window.attributes("-alpha", alpha)
        self.window.configure(bg=BG)
        self.text = _make_text(self.window, self.fonts)
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

    def fill(self, layout: Layout) -> None:
        """Vẽ một bố cục (cỡ chữ + 1 hoặc 2 cột) đã tính bằng ``panel_layout.fit_layout``."""
        self.fonts.resize(layout.font_size)
        if len(layout.columns) == 1:
            fill_text(self.text, list(layout.columns[0]))
        else:
            fill_columns(self.text, *layout.columns)

    def move(self, x: int, y: int) -> None:
        self.window.geometry(f"+{x}+{y}")

    def size(self) -> tuple[int, int]:
        self.window.update_idletasks()
        return self.window.winfo_reqwidth(), self.window.winfo_reqheight()

    def work_area(self) -> Area:
        """Vùng làm việc (trừ taskbar) của màn hình đang chứa khung, px thật (process DPI-aware)."""
        override = os.environ.get(WORK_AREA_ENV, "")
        width, _, height = override.lower().partition("x")
        if width.isdigit() and height.isdigit():
            return 0, 0, int(width), int(height)
        info = _MonitorInfo(cbSize=ctypes.sizeof(_MonitorInfo))
        monitor = _user32.MonitorFromWindow(self.hwnd, MONITOR_DEFAULTTONEAREST)
        if monitor and _user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
            r = info.rcWork
            return r.left, r.top, r.right, r.bottom
        return 0, 0, self.window.winfo_screenwidth(), self.window.winfo_screenheight()


def _make_text(parent: tk.Misc, fonts: OverlayFonts) -> tk.Text:
    text = tk.Text(parent, bg=BG, bd=0, highlightthickness=0, font=fonts.normal,
                   padx=10, pady=8, wrap="none", cursor="arrow")
    for tag, color in COLORS.items():
        text.tag_configure(tag, foreground=color)
    text.tag_configure(TITLE, foreground=COLORS[TITLE], font=fonts.bold)
    text.tag_configure(ALERT, foreground="#ffffff", background=ALERT_BG, font=fonts.alert)
    text.pack()
    return text


def fill_text(widget: tk.Text, lines: list[tuple[str, ...]]) -> None:
    widget.configure(state="normal")
    widget.delete("1.0", "end")
    for line in lines:
        widget.insert("end", line[0] + "\n", line[1])
    widget.delete("end-2c", "end-1c")  # bỏ dòng trống cuối
    width = max(display_width(line[0]) for line in lines)
    widget.configure(state="disabled", width=width + 1, height=len(lines))


def fill_columns(widget: tk.Text, left: tuple[tuple[str, ...], ...],
                 right: tuple[tuple[str, ...], ...]) -> None:
    """Hai cột trong cùng một ô chữ: cột trái được đệm khoảng trắng (không tô màu) cho thẳng."""
    left_width = max((display_width(line[0]) for line in left), default=0)
    right_width = max((display_width(line[0]) for line in right), default=0)
    rows = max(len(left), len(right))
    widget.configure(state="normal")
    widget.delete("1.0", "end")
    for i in range(rows):
        text = left[i][0] if i < len(left) else ""
        if i < len(left):
            widget.insert("end", text, left[i][1])
        widget.insert("end", " " * (left_width - display_width(text) + COLUMN_GAP))
        if i < len(right):
            widget.insert("end", right[i][0], right[i][1])
        widget.insert("end", "\n")
    widget.delete("end-2c", "end-1c")
    widget.configure(state="disabled", width=left_width + COLUMN_GAP + right_width + 1, height=rows)
