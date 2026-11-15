"""DPI theo từng màn hình (per-monitor v2).

Tiến trình báo Windows là per-monitor-v2 aware, nên khi một khung sang màn hình có mức scale
khác, Windows không phóng to/thu nhỏ ảnh của nó (chữ không bị mờ). Đổi lại overlay phải tự đổi
cỡ chữ: mỗi khung dùng font tính bằng pixel theo DPI của màn hình đang chứa nó
(``GetDpiForWindow``), thay vì point theo ``tk scaling`` (chỉ một giá trị cho cả tiến trình).
"""
from __future__ import annotations

import ctypes

BASE_DPI = 96  # 100%
POINTS_PER_INCH = 72
MIN_DPI, MAX_DPI = 48, 960
DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4
PROCESS_PER_MONITOR_DPI_AWARE = 2
PROCESS_SYSTEM_DPI_AWARE = 1


def clamp_dpi(dpi: int | None, fallback: int = BASE_DPI) -> int:
    """DPI hợp lệ; 0/None/giá trị lạ -> ``fallback``."""
    if not dpi or dpi < MIN_DPI or dpi > MAX_DPI:
        return fallback
    return int(dpi)


def font_pixels(points: int, dpi: int) -> int:
    """Cỡ font Tk theo pixel (số âm) cho ``points`` ở ``dpi``: 10pt @96 -> -13, @144 -> -20."""
    return -max(round(points * dpi / POINTS_PER_INCH), 1)


def scale_for(dpi: int) -> float:
    """Hệ số so với 100% (dùng cho lề, bo góc, viền)."""
    return dpi / BASE_DPI


def enable_per_monitor_awareness() -> str:
    """Bật per-monitor v2, lùi dần về per-monitor v1 rồi system-aware. Trả về mức đã bật."""
    user32 = getattr(ctypes, "windll", None) and ctypes.windll.user32
    if not user32:
        return "none"
    try:
        if user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(
                DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2)):
            return "per-monitor-v2"
    except (AttributeError, OSError):
        pass
    for level, name in ((PROCESS_PER_MONITOR_DPI_AWARE, "per-monitor"),
                        (PROCESS_SYSTEM_DPI_AWARE, "system")):
        try:
            if ctypes.windll.shcore.SetProcessDpiAwareness(level) == 0:
                return name
        except (AttributeError, OSError):
            break
    try:
        return "system" if user32.SetProcessDPIAware() else "none"
    except (AttributeError, OSError):
        return "none"


def window_dpi(hwnd: int) -> int:
    """DPI của màn hình chứa cửa sổ (Windows 10 1607+); không có thì DPI hệ thống / 96."""
    try:
        user32 = ctypes.windll.user32
        dpi = user32.GetDpiForWindow(ctypes.c_void_p(hwnd))
        if not dpi:
            dpi = user32.GetDpiForSystem()
        return clamp_dpi(dpi)
    except (AttributeError, OSError):
        return BASE_DPI
