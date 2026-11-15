"""Các khung overlay (chi tiết, việc cần làm, chú giải) và vòng đọc dữ liệu.

Lưu ý: overlay chỉ hiện trên game khi game chạy ở chế độ Windowed/Borderless,
không hiện được trên chế độ Exclusive Fullscreen.
"""
from __future__ import annotations

import time
import tkinter as tk
from pathlib import Path
from typing import Callable

from .action_plan import build_steps
from .config import DEFAULT_CONFIG_FILE, DEFAULT_POSITION, load_config, save_position, update_config
from .day_log import DEFAULT_DAY_LOG, DayTracker, append_day, load_day_keys, observe_day
from .fever_calibration import FeverTracker, load_fever_stats, observe, save_fever_stats
from .formatter import DIM, NORMAL, WARN, format_state
from .i18n import choose_language, get_language, set_language, t, windows_ui_language
from .legend import legend_lines
from .live_source import LiveSource
from .merchant_advice import evaluate_merchant, merchant_active
from .overlay_windows import OverlayWindow, key_is_down, measure_metrics
from .panel_layout import MIN_FONT, Layout, fit_layout
from .relic_names import load_relic_texts
from .run_log import DEFAULT_RUN_LOG, append_run, load_runs, record_from_state, summary_line
from .save_reader import RunState, SaveReadError, find_run_save, load_run_state
from .settings import FONT_MAX, Settings, language_override, panel_visibility
from .text_format import SEP

HOTKEY_POLL_MS = 80
PANEL_MARGIN = 20  # khoảng cách các khung tới mép vùng làm việc của màn hình (px)
STATUS_LINES = 3  # dòng trống + trạng thái + phím tắt ở cuối khung chi tiết, không bao giờ cắt
LIVE_FRESH_SECONDS = 3.0  # dữ liệu trực tiếp cũ hơn mức này -> quay về file save

VK_SETTINGS, VK_TOGGLE_LEGEND = 0x75, 0x76  # F6, F7
VK_TOGGLE_VISIBLE, VK_TOGGLE_DRAG, VK_QUIT = 0x77, 0x78, 0x79  # F8, F9, F10


class Overlay:
    def __init__(self, master: tk.Misc, settings: Settings, save_dir: Path, poll_ms: int,
                 x: int, y: int, names: dict[str, str] | None = None,
                 config_file: Path = DEFAULT_CONFIG_FILE,
                 live_factory: Callable[[], LiveSource] = LiveSource,
                 on_settings: Callable[[], None] = lambda: None,
                 on_quit: Callable[[], None] = lambda: None) -> None:
        self.master = master
        self.settings = settings
        self.save_dir = save_dir
        self.poll_ms = poll_ms
        self.names = names or {}
        self.config_file = config_file
        self._live_factory = live_factory
        self._on_settings = on_settings
        self._on_quit = on_quit
        self.live: LiveSource | None = None
        self._system_lang = windows_ui_language()
        # Ngôn ngữ game lần trước: dùng ngay từ đầu, trước khi kết nối được với game.
        self._saved_game_lang = load_config(config_file).get("game_lang")
        set_language(choose_language(language_override(settings), self._saved_game_lang,
                                     self._system_lang))
        self.texts = load_relic_texts(lang=get_language())  # tên chính thức từ lần kết nối trước
        self._fever_tracker = FeverTracker()
        self._fever_stats = load_fever_stats(config_file)
        self._runs = load_runs(DEFAULT_RUN_LOG)
        self._day_tracker = DayTracker()
        self._day_keys = load_day_keys(DEFAULT_DAY_LOG)
        self.state: RunState | None = None
        self.status = t("status.searching")
        self._last_sig: tuple[str, int] | None = None
        self._last_live_state: RunState | None = None
        self._keys_down: set[int] = set()
        self._hidden = False  # F8
        self._legend_on = settings.show_legend  # F7
        self._is_live = False  # True khi đang hiển thị dữ liệu đọc trực tiếp từ game
        self._drag_mode = False
        self._drag_origin = (0, 0)
        self._running = True

        self.metrics = measure_metrics(master, range(MIN_FONT, FONT_MAX + 1))
        self.details = OverlayWindow(master, settings.font_size, settings.alpha)
        self.details.move(x, y)
        self.details.text.bind("<ButtonPress-1>", self._on_drag_start)
        self.details.text.bind("<B1-Motion>", self._on_drag_move)
        self.panel = OverlayWindow(master, settings.font_size, settings.alpha)  # "Việc cần làm"
        self.legend = OverlayWindow(master, settings.font_size, settings.alpha)  # "Chú giải" (F7)
        self._set_live(settings.live)
        self.render()
        self._update_visibility()

    # ---------- cài đặt ----------
    def apply_settings(self, settings: Settings) -> None:
        """Áp dụng ngay cài đặt mới (từ màn hình cài đặt) khi overlay đang chạy."""
        old, self.settings = self.settings, settings
        if settings.show_legend != old.show_legend:
            self._legend_on = settings.show_legend
        if settings.opacity != old.opacity:
            for window in (self.details, self.panel, self.legend):
                window.set_alpha(settings.alpha)
        if settings.live != old.live:
            self._set_live(settings.live)
        self._update_language()
        self.render()
        self._update_visibility()

    def reset_position(self) -> None:
        self.details.move(*DEFAULT_POSITION)
        save_position(self.config_file, *DEFAULT_POSITION)

    def shutdown(self) -> None:
        """Dừng vòng lặp + đọc trực tiếp, nhớ vị trí. Cửa sổ do root hủy."""
        self._running = False
        self._save_position()
        self._set_live(False)

    def _set_live(self, enabled: bool) -> None:
        if enabled and self.live is None:
            self.live = self._live_factory()
            self.live.start()
        elif not enabled and self.live is not None:
            self.live.stop()
            self.live = None
            self._is_live = False
            self._last_sig = None  # buộc đọc lại file save ngay

    def _update_visibility(self) -> None:
        details, todo, legend = panel_visibility(self.settings, self._hidden, self._legend_on)
        self.details.show(details)
        self.panel.show(todo)
        self.legend.show(legend)
        if legend:
            self._place_legend()

    def _fit(self, window: OverlayWindow, lines: list, pinned_tail: int = 0) -> Layout:
        """Co khung cho vừa vùng làm việc của màn hình đang chứa nó, rồi vẽ."""
        left, top, right, bottom = window.work_area()
        layout = fit_layout(lines, self.metrics, right - left - 2 * PANEL_MARGIN,
                            bottom - top - 2 * PANEL_MARGIN, self.settings.font_size,
                            pinned_tail=pinned_tail)
        window.fill(layout)
        return layout

    # ---------- vòng lặp ----------
    def start(self) -> None:
        self.master.after(0, self._poll_save)
        self.master.after(0, self._poll_hotkeys)

    def _key_pressed_once(self, vk: int) -> bool:
        """True đúng một lần mỗi khi phím vừa được nhấn xuống (phát hiện cạnh)."""
        down = key_is_down(vk)
        was_down = vk in self._keys_down
        if down:
            self._keys_down.add(vk)
        else:
            self._keys_down.discard(vk)
        return down and not was_down

    def _poll_hotkeys(self) -> None:
        if not self._running:
            return
        if self._key_pressed_once(VK_QUIT):
            self._on_quit()
            return
        if self._key_pressed_once(VK_SETTINGS):
            self._on_settings()
        if self._key_pressed_once(VK_TOGGLE_VISIBLE):
            self._hidden = not self._hidden
            self._update_visibility()
        if self._key_pressed_once(VK_TOGGLE_LEGEND):
            self._legend_on = not self._legend_on
            self._update_visibility()
        if self._key_pressed_once(VK_TOGGLE_DRAG):
            self._drag_mode = not self._drag_mode
            self.details.set_click_through(not self._drag_mode)
            if not self._drag_mode:  # vừa khóa vị trí -> nhớ cho lần mở sau
                self._save_position()
            self.render()
        self.master.after(HOTKEY_POLL_MS, self._poll_hotkeys)

    def _place_legend(self) -> None:
        """Khung chú giải ở giữa mép trên vùng làm việc của màn hình."""
        self._fit(self.legend, legend_lines())
        left, top, right, _ = self.legend.work_area()
        width, _ = self.legend.size()
        self.legend.move(max(left + (right - left - width) // 2, left), top + PANEL_MARGIN)

    def _save_position(self) -> None:
        save_position(self.config_file, self.details.window.winfo_x(),
                      self.details.window.winfo_y())

    def _poll_save(self) -> None:
        if not self._running:
            return
        self._refresh_state()
        self.master.after(self.poll_ms, self._poll_save)

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
        if state is not self._last_live_state:
            self._last_live_state = state
            self.state = state
            self._track_fever(state)
            self._log_finished_run(state)
            self._log_day(state)
            self._last_sig = None  # khi mất live, buộc đọc lại file
            self._is_live = True
            self._follow_game_language()
            self._set_status(t("status.live", time=time.strftime("%H:%M:%S")))
        return True

    def _follow_game_language(self) -> None:
        """Nhớ ngôn ngữ game đang dùng và đổi overlay theo (trừ khi cài đặt chọn sẵn)."""
        game_lang = self.live.language() if self.live is not None else None
        if game_lang and game_lang != self._saved_game_lang:  # nhớ cho lần mở sau
            self._saved_game_lang = game_lang
            update_config(self.config_file, game_lang=game_lang)
        self._update_language()

    def _update_language(self) -> None:
        game_lang = self.live.language() if self.live is not None else None
        lang = choose_language(language_override(self.settings),
                               game_lang or self._saved_game_lang, self._system_lang)
        if lang == get_language():
            return
        set_language(lang)
        self.texts = load_relic_texts(lang=lang)
        if self.legend.window.winfo_viewable():
            self._place_legend()

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
            self._set_status(t("status.no_save", folder=self.save_dir))
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
            self._set_status(t("status.save_busy"))
            return
        self._last_sig = sig
        self._log_finished_run(self.state)
        live_note = f"{SEP}{self.live.status}" if self.live is not None else ""
        self._set_status(t("status.save_read", time=time.strftime("%H:%M:%S")) + live_note)

    def _set_status(self, status: str) -> None:
        self.status = status
        self.render()

    # ---------- vẽ ----------
    def render(self) -> None:
        odds, multiplier, shop_sim, quota, grade_odds = ({}, 1.5, None, 0.0, None)
        next_quota, reroll_text, relic_rank, schedule = 0.0, "", None, ()
        texts = self.texts
        if self.live is not None:
            texts = self.live.texts(get_language()) or texts  # tên chính thức mới nhất từ game
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
                             summary_line(self._runs), relic_rank, schedule, keep_priority=True)
        hint = t("hint.drag") if self._drag_mode else t("hint.keys")
        lines = lines + [("", NORMAL), (self.status, DIM), (hint, WARN if self._drag_mode else DIM)]
        self._fit(self.details, lines, pinned_tail=STATUS_LINES)
        self._keep_details_on_screen()
        steps = build_steps(self.state, odds, multiplier, quota, grade_odds, shop_sim, names, merchant,
                            fever_strikes, next_quota, reroll_text, relic_rank, schedule)
        self._fit(self.panel, steps)
        left, top, right, _ = self.panel.work_area()  # sát mép phải vùng làm việc
        width, _ = self.panel.size()
        self.panel.move(max(right - width - PANEL_MARGIN, left), top + PANEL_MARGIN)

    def _keep_details_on_screen(self) -> None:
        """Đẩy khung chi tiết vào trong vùng làm việc nếu nó lòi ra ngoài (sau khi co/kéo)."""
        left, top, right, bottom = self.details.work_area()
        width, height = self.details.size()
        x, y = self.details.window.winfo_x(), self.details.window.winfo_y()
        new_x = max(left, min(x, right - width))
        new_y = max(top, min(y, bottom - height))
        if (new_x, new_y) != (x, y):
            self.details.move(new_x, new_y)

    # ---------- kéo thả khi bật F9 ----------
    def _on_drag_start(self, event: tk.Event) -> None:
        window = self.details.window
        self._drag_origin = (event.x_root - window.winfo_x(), event.y_root - window.winfo_y())

    def _on_drag_move(self, event: tk.Event) -> None:
        if not self._drag_mode:
            return
        dx, dy = self._drag_origin
        self.details.move(event.x_root - dx, event.y_root - dy)
