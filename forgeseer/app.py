"""Ghép màn hình cài đặt với overlay: một root Tk (chính là cửa sổ cài đặt), một mainloop.

- Mở: hiện cài đặt (trừ khi đã chọn bỏ qua) -> "Bắt đầu" lưu cài đặt, thu nhỏ cửa sổ xuống
  taskbar và bật overlay.
- Bấm biểu tượng trên taskbar hoặc F6: hiện lại cài đặt, overlay vẫn chạy, đổi gì áp dụng ngay.
- Nút X: chỉ thu nhỏ. "Thoát" hoặc F10: tắt hết (kể cả đọc trực tiếp).
"""
from __future__ import annotations

import tkinter as tk
from pathlib import Path

from .config import DEFAULT_CONFIG_FILE, DEFAULT_POSITION, load_config, save_position
from .fever_calibration import load_fever_stats
from .i18n import choose_language, set_language, windows_ui_language
from .live_source import DEFAULT_MULTIPLIER, LiveSource
from .overlay import Overlay
from .overlay_windows import enable_dpi_awareness
from .save_reader import RunState, SaveReadError, find_run_save, load_run_state
from .settings import Settings, language_override, save_settings
from .settings_window import SettingsWindow
from .sim_tab import SimSource
from .simulator import build_input
from .update_check import UpdateChecker

UPDATE_POLL_MS = 500


def sim_source(state: RunState | None, live: LiveSource | None, fever_strikes: int) -> SimSource | None:
    """Simulation input from a state plus, when it came from the game, the game's numbers."""
    if state is None:
        return None
    quota, schedule, table, multiplier = 0.0, (), None, DEFAULT_MULTIPLIER
    if live is not None:
        _, multiplier = live.odds()
        quota, schedule, table = live.quota(), live.quota_schedule(), live.grade_odds()
    inp = build_input(state, quota, schedule, table, multiplier, fever_strikes)
    return SimSource(inp=inp, live=live is not None, day=state.round)


class App:
    def __init__(self, root: tk.Tk, settings: Settings, save_dir: Path, poll_ms: int,
                 x: int, y: int, names: dict[str, str] | None = None,
                 config_file: Path = DEFAULT_CONFIG_FILE) -> None:
        self.root = root
        self.save_dir = save_dir
        self.poll_ms = poll_ms
        self.position = (x, y)
        self.names = names
        self.config_file = config_file
        self.overlay: Overlay | None = None
        self._preview_language(settings)
        self.window = SettingsWindow(root, settings, on_change=self._changed,
                                     on_start=self.start, on_quit=self.quit,
                                     on_reset_position=self._reset_position,
                                     on_close=self._close, sim_source=self._sim_source)
        self._updates: UpdateChecker | None = None
        if settings.check_updates:
            self._updates = UpdateChecker().start()
            root.after(UPDATE_POLL_MS, self._poll_update)

    def _poll_update(self) -> None:
        if self._updates is None:
            return
        if not self._updates.done:
            self.root.after(UPDATE_POLL_MS, self._poll_update)
            return
        self.window.set_update(self._updates.result)

    def _sim_source(self) -> SimSource | None:
        """Latest snapshot for the simulation: the overlay's live state if it has a fresh one,
        else the newest save file. Only reads what the overlay already holds."""
        fever = load_fever_stats(self.config_file).strikes
        overlay = self.overlay
        live = getattr(overlay, "live", None)
        if live is not None and getattr(overlay, "_is_live", False):
            return sim_source(overlay.state, live, fever)
        state = overlay.state if overlay is not None else None
        if state is None:
            path = find_run_save(self.save_dir)
            try:
                state = load_run_state(path) if path is not None else None
            except SaveReadError:
                state = None
        return sim_source(state, None, fever)

    def _preview_language(self, settings: Settings) -> None:
        """Trước khi overlay chạy: màn hình cài đặt dùng ngôn ngữ đang chọn."""
        set_language(choose_language(language_override(settings),
                                     load_config(self.config_file).get("game_lang"),
                                     windows_ui_language()))

    def _changed(self, settings: Settings) -> None:
        if self.overlay is None:
            self._preview_language(settings)
        else:
            self.overlay.apply_settings(settings)

    def start(self, settings: Settings) -> None:
        save_settings(self.config_file, settings)
        if self.overlay is None:
            self.overlay = Overlay(self.root, settings, self.save_dir, self.poll_ms,
                                   *self.position, self.names, config_file=self.config_file,
                                   on_settings=self.window.show, on_quit=self.quit)
            self.overlay.start()
            self.window.mark_started()
        else:
            self.overlay.apply_settings(settings)
        self.window.minimize()

    def _close(self) -> None:
        """Nút X: đang chơi thì chỉ thu nhỏ; chưa bấm "Bắt đầu" thì không có gì để giữ lại."""
        if self.overlay is None:
            self.quit()
            return
        save_settings(self.config_file, self.window.settings)
        self.window.minimize()

    def _reset_position(self) -> None:
        self.position = DEFAULT_POSITION
        if self.overlay is not None:
            self.overlay.reset_position()
        else:
            save_position(self.config_file, *DEFAULT_POSITION)

    def quit(self) -> None:
        if self.overlay is not None:
            save_settings(self.config_file, self.window.settings)
            self.overlay.shutdown()
        self.root.destroy()


def run_app(save_dir: Path, poll_ms: int, x: int, y: int, settings: Settings,
            names: dict[str, str] | None = None, show_settings: bool = True) -> None:
    enable_dpi_awareness()
    root = tk.Tk()
    app = App(root, settings, save_dir, poll_ms, x, y, names)
    if show_settings:
        app.window.show()
    else:
        app.start(settings)  # vào thẳng overlay, cài đặt nằm sẵn dưới taskbar
    root.mainloop()
