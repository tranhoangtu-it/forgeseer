"""Cửa sổ trong suốt, luôn nằm trên, cho chuột bấm xuyên qua (Win32) dùng cho các khung overlay.

Mỗi khung vẽ lên một Canvas (``panel_canvas``) với nền bo góc; phần ngoài góc bo dùng màu khóa
``-transparentcolor`` nên trong suốt hẳn. Font tính bằng pixel theo DPI của màn hình đang chứa
khung (``dpi``), nên kéo khung sang màn hình có mức scale khác thì chữ vẫn sắc và đúng cỡ.
"""
from __future__ import annotations

import ctypes
import os
import tkinter as tk
import tkinter.font as tkfont
from ctypes import wintypes

from .dpi import BASE_DPI, enable_per_monitor_awareness, font_pixels, scale_for, window_dpi
from .panel_canvas import TRANSPARENT_KEY, PanelCanvas
from .panel_layout import FontMetrics, Layout

FONT_FAMILY = "Consolas"
ALERT_EXTRA_POINTS = 4  # chữ cảnh báo to hơn chữ thường

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


def enable_dpi_awareness() -> str:
    """Per-monitor v2 (lùi dần về v1 / system-aware); gọi trước khi tạo root Tk."""
    return enable_per_monitor_awareness()


def key_is_down(vk: int) -> bool:
    return bool(_user32.GetAsyncKeyState(vk) & 0x8000)


def measure_metrics(master: tk.Misc, sizes: range, dpi: int = BASE_DPI) -> dict[int, FontMetrics]:
    """Chiều cao dòng và bề rộng một cột của font overlay ở từng cỡ (point) tại ``dpi``."""
    metrics = {}
    for size in sizes:
        font = tkfont.Font(master, family=FONT_FAMILY, size=font_pixels(size, dpi))
        metrics[size] = FontMetrics(font.metrics("linespace"), font.measure("0"))
    return metrics


class OverlayFonts:
    """Font của một khung; mỗi khung tự co cỡ chữ và theo DPI màn hình riêng nên không dùng chung."""

    def __init__(self, master: tk.Misc, size: int, dpi: int = BASE_DPI) -> None:
        self.size, self.dpi = size, dpi
        self.normal = tkfont.Font(master, family=FONT_FAMILY)
        self.bold = tkfont.Font(master, family=FONT_FAMILY, weight="bold")
        self.alert = tkfont.Font(master, family=FONT_FAMILY, weight="bold")
        self._apply()

    def _apply(self) -> None:
        px = font_pixels(self.size, self.dpi)
        self.normal.configure(size=px)
        self.bold.configure(size=px)
        self.alert.configure(size=font_pixels(self.size + ALERT_EXTRA_POINTS, self.dpi))

    def resize(self, size: int, dpi: int | None = None) -> None:
        dpi = self.dpi if dpi is None else dpi
        if (size, dpi) == (self.size, self.dpi):
            return
        self.size, self.dpi = size, dpi
        self._apply()


class OverlayWindow:
    """Một khung overlay: Toplevel không viền + Canvas, mặc định cho chuột bấm xuyên qua."""

    def __init__(self, master: tk.Misc, font_size: int, alpha: float) -> None:
        self.alpha = alpha
        self.window = tk.Toplevel(master)
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", True)
        self.window.configure(bg=TRANSPARENT_KEY)
        self.panel = PanelCanvas(self.window)
        self.canvas = self.panel.canvas
        self.window.update_idletasks()
        self.hwnd = _user32.GetParent(self.window.winfo_id()) or self.window.winfo_id()
        self.fonts = OverlayFonts(master, font_size, self.dpi())
        self.set_click_through(True)

    def dpi(self) -> int:
        """DPI của màn hình đang chứa khung (đổi khi khung bị kéo sang màn hình khác)."""
        return window_dpi(self.hwnd)

    def set_click_through(self, enabled: bool) -> None:
        style = _user32.GetWindowLongPtrW(self.hwnd, GWL_EXSTYLE)
        style |= WS_EX_LAYERED | WS_EX_TOOLWINDOW
        style = style | WS_EX_TRANSPARENT if enabled else style & ~WS_EX_TRANSPARENT
        _user32.SetWindowLongPtrW(self.hwnd, GWL_EXSTYLE, style)
        # Tk tự đặt lại thuộc tính layered khi đổi style -> gán lại cho chắc.
        self.window.attributes("-alpha", self.alpha)
        self.window.attributes("-transparentcolor", TRANSPARENT_KEY)

    def set_alpha(self, alpha: float) -> None:
        self.alpha = alpha
        self.window.attributes("-alpha", alpha)

    def show(self, shown: bool) -> None:
        if shown:
            self.window.deiconify()
        else:
            self.window.withdraw()

    def fill(self, layout: Layout, metrics: FontMetrics, dpi: int) -> None:
        """Vẽ một bố cục (cỡ chữ + 1 hoặc 2 cột) đã tính bằng ``panel_layout.fit_layout``;
        ``metrics``/``dpi``: số đo font của đúng màn hình đã dùng để tính bố cục."""
        self.fonts.resize(layout.font_size, dpi)
        self.panel.draw(layout, self.fonts, metrics, scale_for(dpi))

    def flash(self, color: str, cycles: int = 3, period_ms: int = 220) -> None:
        self.panel.flash(color, cycles, period_ms)

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

