"""Cửa sổ overlay trong suốt, luôn nằm trên, cho chuột bấm xuyên qua (Windows).

Lưu ý: overlay chỉ hiện trên game khi game chạy ở chế độ Windowed/Borderless,
không hiện được trên chế độ Exclusive Fullscreen.
"""
from __future__ import annotations

import ctypes
import time
import tkinter as tk
from ctypes import wintypes
from pathlib import Path

from .config import DEFAULT_CONFIG_FILE, save_position
from .day_log import DEFAULT_DAY_LOG, DayTracker, append_day, load_day_keys, observe_day
from .formatter import DIM, GOOD, NORMAL, TITLE, WARN, format_state
from .action_plan import ALERT, build_steps
from .fever_calibration import FeverTracker, load_fever_stats, observe, save_fever_stats
from .legend import legend_lines
from .live_source import LiveSource
from .merchant_advice import evaluate_merchant, merchant_active
from .relic_names import load_relic_texts
from .run_log import DEFAULT_RUN_LOG, append_run, load_runs, record_from_state, summary_line
from .save_reader import RunState, SaveReadError, find_run_save, load_run_state
from .text_format import SEP

BG = "#101014"
COLORS = {TITLE: "#f0c060", NORMAL: "#e8e8e8", GOOD: "#7ee08a", WARN: "#ff6b5b", DIM: "#9a9aa8"}
FONT = ("Consolas", 10)
ALERT_FONT = ("Consolas", 14, "bold")
ALERT_BG = "#b01818"
ALPHA = 0.85
HOTKEY_POLL_MS = 80
PANEL_MARGIN = 20  # khoảng cách khung "Việc cần làm" tới mép phải/trên màn hình (px)
LIVE_FRESH_SECONDS = 3.0  # dữ liệu trực tiếp cũ hơn mức này -> quay về file save

GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080  # ẩn khỏi taskbar / Alt+Tab
VK_TOGGLE_LEGEND = 0x76  # F7
VK_TOGGLE_VISIBLE, VK_TOGGLE_DRAG, VK_QUIT = 0x77, 0x78, 0x79  # F8, F9, F10
HINT_TEXT = f"F7 chú giải{SEP}F8 ẩn{SEP}F9 di chuyển{SEP}F10 thoát"
DRAG_HINT_TEXT = "F9: khóa vị trí"
LIVE_STATUS_PREFIX = "Đọc trực tiếp lúc"

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


def _make_text(parent: tk.Misc) -> tk.Text:
    text = tk.Text(parent, bg=BG, bd=0, highlightthickness=0, font=FONT,
                   padx=10, pady=8, wrap="none", cursor="arrow")
    for tag, color in COLORS.items():
        text.tag_configure(tag, foreground=color)
    text.tag_configure(TITLE, foreground=COLORS[TITLE], font=FONT + ("bold",))
    text.tag_configure(ALERT, foreground="#ffffff", background=ALERT_BG, font=ALERT_FONT)
    text.pack()
    return text


def _fill_text(widget: tk.Text, lines: list[tuple[str, str]]) -> None:
    widget.configure(state="normal")
    widget.delete("1.0", "end")
    for text, tag in lines:
        widget.insert("end", text + "\n", tag)
    widget.delete("end-2c", "end-1c")  # bỏ dòng trống cuối
    width = max(len(text) for text, _ in lines)
    widget.configure(state="disabled", width=width + 1, height=len(lines))


def _set_click_through(hwnd: int, window: tk.Misc, enabled: bool) -> None:
    style = _user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
    style |= WS_EX_LAYERED | WS_EX_TOOLWINDOW
    style = style | WS_EX_TRANSPARENT if enabled else style & ~WS_EX_TRANSPARENT
    _user32.SetWindowLongPtrW(hwnd, GWL_EXSTYLE, style)
    # Tk tự đặt lại alpha khi đổi style layered -> gán lại cho chắc.
    window.attributes("-alpha", ALPHA)


class Overlay:
    def __init__(self, root: tk.Tk, save_dir: Path, poll_ms: int, x: int, y: int,
                 names: dict[str, str] | None = None,
                 config_file: Path = DEFAULT_CONFIG_FILE,
                 live: LiveSource | None = None) -> None:
        self.root = root
        self.live = live
        self.save_dir = save_dir
        self.poll_ms = poll_ms
        self.names = names or {}
        self.texts = load_relic_texts()  # cache tên chính thức từ lần kết nối trước
        self.config_file = config_file
        self._fever_tracker = FeverTracker()
        self._fever_stats = load_fever_stats(config_file)
        self._runs = load_runs(DEFAULT_RUN_LOG)
        self._day_tracker = DayTracker()
        self._day_keys = load_day_keys(DEFAULT_DAY_LOG)
        self.state: RunState | None = None
        self.status = "Đang tìm file save..."
        self._last_sig: tuple[str, int] | None = None
        self._keys_down: set[int] = set()
        self._visible = True
        self._legend_visible = False
        self._is_live = False  # True khi đang hiển thị dữ liệu đọc trực tiếp từ game
        self._drag_mode = False
        self._drag_origin = (0, 0)

        root.overrideredirect(True)
        root.attributes("-topmost", True)
        root.attributes("-alpha", ALPHA)
        root.configure(bg=BG)
        root.geometry(f"+{x}+{y}")

        self.text = _make_text(root)
        self.text.bind("<ButtonPress-1>", self._on_drag_start)
        self.text.bind("<B1-Motion>", self._on_drag_move)

        # Khung "Việc cần làm" ở góc phải màn hình (luôn bấm xuyên qua được).
        self.panel = tk.Toplevel(root)
        self.panel.overrideredirect(True)
        self.panel.attributes("-topmost", True)
        self.panel.configure(bg=BG)
        self.panel_text = _make_text(self.panel)

        # Khung "Chú giải" (F7), ẩn lúc đầu, cũng bấm xuyên qua được.
        self.legend = tk.Toplevel(root)
        self.legend.overrideredirect(True)
        self.legend.attributes("-topmost", True)
        self.legend.configure(bg=BG)
        self.legend_text = _make_text(self.legend)
        _fill_text(self.legend_text, legend_lines())

        root.update_idletasks()
        self.panel.update_idletasks()
        self.hwnd = _user32.GetParent(root.winfo_id()) or root.winfo_id()
        self.panel_hwnd = _user32.GetParent(self.panel.winfo_id()) or self.panel.winfo_id()
        self._apply_click_through(True)
        _set_click_through(self.panel_hwnd, self.panel, True)
        self.legend.update_idletasks()
        self.legend_hwnd = _user32.GetParent(self.legend.winfo_id()) or self.legend.winfo_id()
        _set_click_through(self.legend_hwnd, self.legend, True)
        self._place_legend()
        self.legend.withdraw()
        self.render()

    # ---------- Win32 ----------
    def _apply_click_through(self, enabled: bool) -> None:
        _set_click_through(self.hwnd, self.root, enabled)

    def _key_pressed_once(self, vk: int) -> bool:
        """True đúng một lần mỗi khi phím vừa được nhấn xuống (phát hiện cạnh)."""
        down = bool(_user32.GetAsyncKeyState(vk) & 0x8000)
        was_down = vk in self._keys_down
        if down:
            self._keys_down.add(vk)
        else:
            self._keys_down.discard(vk)
        return down and not was_down

    # ---------- vòng lặp ----------
    def start(self) -> None:
        self.root.after(0, self._poll_save)
        self.root.after(0, self._poll_hotkeys)

    def _poll_hotkeys(self) -> None:
        if self._key_pressed_once(VK_QUIT):
            self._save_position()
            if self.live is not None:
                self.live.stop()
            self.root.destroy()
            return
        if self._key_pressed_once(VK_TOGGLE_VISIBLE):
            self._visible = not self._visible
            for window in (self.root, self.panel):
                if self._visible:
                    window.deiconify()
                else:
                    window.withdraw()
            self._show_legend(self._visible and self._legend_visible)
        if self._key_pressed_once(VK_TOGGLE_LEGEND):
            self._legend_visible = not self._legend_visible
            self._show_legend(self._visible and self._legend_visible)
        if self._key_pressed_once(VK_TOGGLE_DRAG):
            self._drag_mode = not self._drag_mode
            self._apply_click_through(not self._drag_mode)
            if not self._drag_mode:  # vừa khóa vị trí -> nhớ cho lần mở sau
                self._save_position()
            self.render()
        self.root.after(HOTKEY_POLL_MS, self._poll_hotkeys)

    def _show_legend(self, shown: bool) -> None:
        if shown:
            self.legend.deiconify()
            self._place_legend()
        else:
            self.legend.withdraw()

    def _place_legend(self) -> None:
        """Khung chú giải ở giữa mép trên màn hình."""
        self.legend.update_idletasks()
        x = (self.legend.winfo_screenwidth() - self.legend.winfo_reqwidth()) // 2
        self.legend.geometry(f"+{max(x, 0)}+{PANEL_MARGIN}")

    def _save_position(self) -> None:
        save_position(self.config_file, self.root.winfo_x(), self.root.winfo_y())

    def _poll_save(self) -> None:
        self._refresh_state()
        self.root.after(self.poll_ms, self._poll_save)

    def _refresh_state(self) -> None:
        if self._refresh_from_live():
            return
        self._last_live_state = None
        self._is_live = False
        self._refresh_from_file()

    def _refresh_from_live(self) -> bool:
        """True nếu đã dùng dữ liệu trực tiếp còn mới."""
        if self.live is None:
            return False
        state, age = self.live.latest()
        if state is None or age is None or age > LIVE_FRESH_SECONDS:
            return False
        if state is not getattr(self, "_last_live_state", None):
            self._last_live_state = state
            self.state = state
            self._track_fever(state)
            self._log_finished_run(state)
            self._log_day(state)
            self._last_sig = None  # khi mất live, buộc đọc lại file
            self._is_live = True
            self._set_status(f"{LIVE_STATUS_PREFIX} {time.strftime('%H:%M:%S')}")
        return True

    def _track_fever(self, state: RunState) -> None:
        """Hiệu chỉnh số nhát mỗi đợt Xuất Thần từ dữ liệu trực tiếp (bản chụp ~300ms)."""
        self._fever_tracker, counts = observe(self._fever_tracker, state.swords)
        if counts:
            for count in counts:
                self._fever_stats = self._fever_stats.add(count)
            save_fever_stats(self.config_file, self._fever_stats)

    def _log_finished_run(self, state: RunState) -> None:
        """Lượt vừa kết thúc -> ghi một dòng vào runs.jsonl (mỗi lượt một lần)."""
        if not state.finished:
            return
        record = record_from_state(state)
        if append_run(DEFAULT_RUN_LOG, record, self._runs):
            self._runs = [*self._runs, record]

    def _log_day(self, state: RunState) -> None:
        """Sang ngày mới / kết thúc lượt -> ghi bản chụp cuối ngày vào days.jsonl (mỗi ngày một lần)."""
        quota = self.live.quota() if self.live is not None else 0.0
        self._day_tracker, record = observe_day(self._day_tracker, state, quota)
        if record is not None and append_day(DEFAULT_DAY_LOG, record, self._day_keys):
            self._day_keys = {*self._day_keys, record.key}

    def _refresh_from_file(self) -> None:
        path = find_run_save(self.save_dir)
        if path is None:
            self._set_status(f"Không thấy file save trong {self.save_dir}")
            return
        try:
            sig = (str(path), path.stat().st_mtime_ns)
        except OSError:
            return  # file đang được game thay thế, thử lại lần sau
        if sig == self._last_sig:
            return
        try:
            self.state = load_run_state(path)
        except SaveReadError:
            # Game có thể đang ghi dở; giữ trạng thái cũ, lần poll sau đọc lại.
            self._set_status("Game đang ghi save, chờ...")
            return
        self._last_sig = sig
        self._log_finished_run(self.state)
        live_note = f"{SEP}{self.live.status}" if self.live is not None else ""
        self._set_status(f"Đọc file save lúc {time.strftime('%H:%M:%S')}{live_note}")

    def _set_status(self, status: str) -> None:
        self.status = status
        self.render()

    # ---------- vẽ ----------
    def render(self) -> None:
        odds, multiplier, shop_sim, quota, grade_odds = ({}, 1.5, None, 0.0, None)
        next_quota, reroll_text, relic_rank, schedule = 0.0, "", None, ()
        texts = self.texts
        if self.live is not None:
            texts = self.live.texts() or texts  # tên chính thức mới nhất từ game
            if self._is_live:
                odds, multiplier = self.live.odds()  # tỉ lệ chỉ có ý nghĩa khi đang đọc trực tiếp
                shop_sim = self.live.shop_simulation()
                quota = self.live.quota()
                next_quota = self.live.next_quota()
                schedule = self.live.quota_schedule()
                reroll_text = self.live.reroll_text()
                grade_odds = self.live.grade_odds()
                relic_rank = self.live.relic_rank()
        names = {**self.names, **{k: t.name for k, t in texts.items()}}
        descriptions = {k: t.description for k, t in texts.items()}
        fever_strikes = self._fever_stats.strikes
        merchant = (evaluate_merchant(self.state, odds, multiplier, grade_odds, fever_strikes)
                    if self.state is not None and merchant_active(self.state) else [])
        lines = format_state(self.state, names, odds, multiplier, descriptions, shop_sim,
                             quota, grade_odds, merchant, fever_strikes, next_quota,
                             summary_line(self._runs), relic_rank, schedule)
        hint = DRAG_HINT_TEXT if self._drag_mode else HINT_TEXT
        lines = lines + [("", NORMAL), (self.status, DIM), (hint, WARN if self._drag_mode else DIM)]
        _fill_text(self.text, lines)
        steps = build_steps(self.state, odds, multiplier, quota, grade_odds, shop_sim, names, merchant,
                            fever_strikes, next_quota, reroll_text, relic_rank, schedule)
        _fill_text(self.panel_text, steps)
        self.panel.update_idletasks()  # đặt khung "Việc cần làm" sát mép phải màn hình
        x = self.panel.winfo_screenwidth() - self.panel.winfo_reqwidth() - PANEL_MARGIN
        self.panel.geometry(f"+{x}+{PANEL_MARGIN}")

    # ---------- kéo thả khi bật F9 ----------
    def _on_drag_start(self, event: tk.Event) -> None:
        self._drag_origin = (event.x_root - self.root.winfo_x(), event.y_root - self.root.winfo_y())

    def _on_drag_move(self, event: tk.Event) -> None:
        if not self._drag_mode:
            return
        dx, dy = self._drag_origin
        self.root.geometry(f"+{event.x_root - dx}+{event.y_root - dy}")


def run_overlay(save_dir: Path, poll_ms: int, x: int, y: int,
                names: dict[str, str] | None = None, use_live: bool = True) -> None:
    enable_dpi_awareness()
    live = LiveSource() if use_live else None
    if live is not None:
        live.start()
    root = tk.Tk()
    root.title("ForgeTax Overlay")
    Overlay(root, save_dir, poll_ms, x, y, names, live=live).start()
    root.mainloop()
