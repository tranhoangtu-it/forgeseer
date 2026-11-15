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
from .i18n import choose_language, set_language, windows_ui_language
from .overlay import Overlay
from .overlay_windows import enable_dpi_awareness
from .settings import Settings, language_override, save_settings
from .settings_window import SettingsWindow


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
                                     on_close=self._close)

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
