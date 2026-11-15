"""Màn hình cài đặt lúc mở (cửa sổ thường, có biểu tượng trên taskbar).

Chỉ lo giao diện: đọc/ghi ``Settings`` qua các callback, không tự lưu file hay đụng tới overlay.
Ba tab: Cài đặt, Mô phỏng (``sim_tab``), Thống kê (``stats_tab``); thông báo bản mới (nếu có)
nằm trên cùng.
"""
from __future__ import annotations

import tkinter as tk
import webbrowser
from tkinter import ttk
from typing import Callable

from . import __version__
from .i18n import SUPPORTED, catalog, get_language, t
from .settings import FONT_MAX, FONT_MIN, LANG_AUTO, OPACITY_MAX, OPACITY_MIN, Settings, from_dict
from .sim_tab import SimTab, SourceProvider
from .stats_tab import StatsTab
from .update_check import UpdateInfo

TAB_SETTINGS, TAB_SIM, TAB_STATS = 0, 1, 2

HOTKEYS = (("F6", "hotkey.f6"), ("F7", "hotkey.f7"), ("F8", "hotkey.f8"), ("F9", "hotkey.f9"),
           ("F10", "hotkey.f10"))
PAD = 12
WRAP_PX = 420
TOPMOST_PULSE_MS = 300


def language_choices() -> list[tuple[str, str]]:
    """(mã, tên hiển thị): "Tự động" trước, rồi mỗi ngôn ngữ viết bằng chính ngôn ngữ đó."""
    return [(LANG_AUTO, t("settings.language_auto"))] + [
        (code, catalog(code).get("language.name", code)) for code in SUPPORTED]


class SettingsWindow:
    def __init__(self, root: tk.Tk, settings: Settings,
                 on_change: Callable[[Settings], None], on_start: Callable[[Settings], None],
                 on_quit: Callable[[], None], on_reset_position: Callable[[], None],
                 on_close: Callable[[], None], sim_source: SourceProvider = lambda: None,
                 stats_tab: StatsTab | None = None) -> None:
        self.root = root
        self.sim_tab = SimTab(root, sim_source)
        self.stats_tab = stats_tab or StatsTab()
        self._update: UpdateInfo | None = None
        self._tab = TAB_SETTINGS
        self._notebook: ttk.Notebook | None = None
        self._stats_box: ttk.Frame | None = None
        self._update_box: ttk.Frame | None = None
        self._on_change = on_change
        self._on_start = on_start
        self._on_quit = on_quit
        self._on_reset_position = on_reset_position
        self.started = False
        self._settings = settings
        self._language = settings.language
        self._opacity = tk.IntVar(root, settings.opacity)
        self._font_size = tk.IntVar(root, settings.font_size)
        self._flags = {name: tk.BooleanVar(root, getattr(settings, name)) for name in
                       ("show_details", "show_todo", "show_legend", "live", "skip_settings",
                        "check_updates")}
        self._built_lang = ""
        self._content: ttk.Frame | None = None
        root.title("ForgeSeer")
        root.resizable(False, False)
        root.protocol("WM_DELETE_WINDOW", on_close)
        ttk.Style(root).configure("Primary.TButton", font=("Segoe UI", 10, "bold"))
        self._build()
        root.update_idletasks()  # mở ở giữa màn hình
        x = (root.winfo_screenwidth() - root.winfo_reqwidth()) // 2
        y = (root.winfo_screenheight() - root.winfo_reqheight()) // 3
        root.geometry(f"+{max(x, 0)}+{max(y, 0)}")

    # ---------- trạng thái ----------
    @property
    def settings(self) -> Settings:
        return self._settings

    def _collect(self) -> Settings:
        raw = {"language": self._language, "opacity": self._opacity.get(),
               "font_size": self._font_size.get(),
               **{name: var.get() for name, var in self._flags.items()}}
        return from_dict(raw)

    def _changed(self, *_: object) -> None:
        try:
            settings = self._collect()
        except tk.TclError:  # ô cỡ chữ đang gõ dở
            return
        if settings == self._settings:
            return
        self._settings = settings
        self._opacity_label.configure(text=f"{settings.opacity}%")
        self._on_change(settings)
        if get_language() != self._built_lang:
            self.root.after_idle(self._build)  # đổi ngôn ngữ -> dựng lại chữ trên màn hình

    # ---------- hiện / ẩn ----------
    def show(self) -> None:
        if get_language() != self._built_lang:
            self._build()
        self.root.deiconify()
        # Game (borderless) đang giữ foreground nên lift() thường bị Windows chặn: tạm bật
        # topmost để cửa sổ nổi lên trên game, rồi tắt để không che game khi người chơi bấm vào.
        self.root.attributes("-topmost", True)
        self.root.lift()
        self.root.focus_force()
        self.root.after(TOPMOST_PULSE_MS, lambda: self.root.attributes("-topmost", False))

    def minimize(self) -> None:
        self.root.iconify()

    def mark_started(self) -> None:
        self.started = True
        self._start_button.configure(text=t("settings.resume"))

    def set_update(self, info: UpdateInfo | None) -> None:
        """Newer release found in the background: show the notice (no-op when None)."""
        self._update = info
        self._render_update()

    def select_tab(self, index: int) -> None:
        if self._notebook is not None:
            self._notebook.select(index)

    # ---------- giao diện ----------
    def _build(self) -> None:
        if self._content is not None:
            if self._notebook is not None:
                self._tab = self._notebook.index("current")
            self._content.destroy()
        self._built_lang = get_language()
        outer = ttk.Frame(self.root, padding=PAD)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        self._content = outer

        ttk.Label(outer, text=t("settings.heading"), font=("Segoe UI", 14, "bold")).grid(
            row=0, column=0, sticky="w")
        self._update_box = ttk.Frame(outer)
        self._update_box.grid(row=1, column=0, sticky="ew")
        self._render_update()

        notebook = ttk.Notebook(outer)
        notebook.grid(row=2, column=0, sticky="nsew", pady=(6, 0))
        self._notebook = notebook
        notebook.add(self._build_settings_tab(notebook), text=t("tab.settings"))
        notebook.add(self.sim_tab.build(notebook), text=t("tab.sim"))
        self._stats_box = ttk.Frame(notebook)
        notebook.add(self._stats_box, text=t("tab.stats"))
        self._refresh_stats()
        notebook.select(self._tab)
        notebook.bind("<<NotebookTabChanged>>", self._tab_changed)
        self._build_buttons(outer, row=3)

    def _build_settings_tab(self, notebook: ttk.Notebook) -> ttk.Frame:
        frame = ttk.Frame(notebook, padding=PAD)
        frame.columnconfigure(1, weight=1)
        ttk.Label(frame, text=t("settings.intro"), wraplength=WRAP_PX, justify="left").grid(
            row=1, column=0, columnspan=3, sticky="w", pady=(0, PAD))
        self._build_appearance(frame, row=2)
        self._build_panels(frame, row=5)
        self._build_hotkeys(frame, row=6)
        for row, (name, key) in enumerate((("skip_settings", "settings.skip"),
                                           ("check_updates", "settings.check_updates")), start=7):
            ttk.Checkbutton(frame, text=t(key), variable=self._flags[name],
                            command=self._changed).grid(row=row, column=0, columnspan=3,
                                                        sticky="w", pady=(PAD if row == 7 else 2, 0))
        return frame

    def _tab_changed(self, _event: object) -> None:
        if self._notebook is None:
            return
        self._tab = self._notebook.index("current")
        if self._tab == TAB_STATS:
            self._refresh_stats()  # một lượt có thể vừa kết thúc

    def _refresh_stats(self) -> None:
        box = self._stats_box
        if box is None:
            return
        for child in box.winfo_children():
            child.destroy()
        self.stats_tab.build(box).pack(fill="both", expand=True)

    def _render_update(self) -> None:
        box = self._update_box
        if box is None or not box.winfo_exists():
            return
        for child in box.winfo_children():
            child.destroy()
        info = self._update
        if info is None:
            return
        ttk.Label(box, text=t("update.available", version=info.version, current=__version__),
                  foreground="#1a6e1a").pack(side="left", pady=(4, 0))
        ttk.Button(box, text=t("update.open"),
                   command=lambda: webbrowser.open(info.url)).pack(side="right", pady=(4, 0))

    def _build_appearance(self, frame: ttk.Frame, row: int) -> None:
        choices = language_choices()
        ttk.Label(frame, text=t("settings.language")).grid(row=row, column=0, sticky="w", pady=3)
        combo = ttk.Combobox(frame, state="readonly", values=[name for _, name in choices])
        codes = [code for code, _ in choices]
        combo.current(codes.index(self._language) if self._language in codes else 0)
        combo.grid(row=row, column=1, columnspan=2, sticky="ew", pady=3)

        def picked(_: object) -> None:
            self._language = codes[combo.current()]
            self._changed()
        combo.bind("<<ComboboxSelected>>", picked)

        ttk.Label(frame, text=t("settings.opacity")).grid(row=row + 1, column=0, sticky="w", pady=3)
        ttk.Scale(frame, from_=OPACITY_MIN, to=OPACITY_MAX, variable=self._opacity,
                  command=lambda _v: self._changed()).grid(row=row + 1, column=1, sticky="ew",
                                                           pady=3)
        self._opacity_label = ttk.Label(frame, text=f"{self._opacity.get()}%", width=5)
        self._opacity_label.grid(row=row + 1, column=2, sticky="e")

        ttk.Label(frame, text=t("settings.font_size")).grid(row=row + 2, column=0, sticky="w",
                                                            pady=3)
        ttk.Spinbox(frame, from_=FONT_MIN, to=FONT_MAX, width=5, state="readonly",
                    textvariable=self._font_size, command=self._changed).grid(
            row=row + 2, column=1, sticky="w", pady=3)

    def _build_panels(self, frame: ttk.Frame, row: int) -> None:
        box = ttk.LabelFrame(frame, text=t("settings.panels"), padding=(PAD, 6))
        box.grid(row=row, column=0, columnspan=3, sticky="ew", pady=(PAD, 0))
        for i, (name, key) in enumerate((("show_details", "settings.show_details"),
                                         ("show_todo", "settings.show_todo"),
                                         ("show_legend", "settings.show_legend"),
                                         ("live", "settings.live"))):
            ttk.Checkbutton(box, text=t(key), variable=self._flags[name],
                            command=self._changed).grid(row=i, column=0, sticky="w", pady=1)
        ttk.Button(box, text=t("settings.reset_position"), command=self._on_reset_position).grid(
            row=4, column=0, sticky="w", pady=(6, 0))

    def _build_hotkeys(self, frame: ttk.Frame, row: int) -> None:
        box = ttk.LabelFrame(frame, text=t("settings.hotkeys"), padding=(PAD, 6))
        box.grid(row=row, column=0, columnspan=3, sticky="ew", pady=(PAD, 0))
        for i, (key, text_key) in enumerate(HOTKEYS):
            ttk.Label(box, text=key, width=5, font=("Consolas", 10, "bold")).grid(
                row=i, column=0, sticky="w")
            ttk.Label(box, text=t(text_key)).grid(row=i, column=1, sticky="w")

    def _build_buttons(self, frame: ttk.Frame, row: int) -> None:
        buttons = ttk.Frame(frame)
        buttons.grid(row=row, column=0, columnspan=3, sticky="ew", pady=(PAD, 0))
        ttk.Button(buttons, text=t("settings.quit"), command=self._on_quit).pack(side="left")
        label = t("settings.resume") if self.started else t("settings.start")
        self._start_button = ttk.Button(buttons, text=label, style="Primary.TButton",
                                        command=self._start)
        self._start_button.pack(side="right")
        self._start_button.focus_set()
        self.root.bind("<Return>", lambda _e: self._start())

    def _start(self) -> None:
        self._changed()
        self._on_start(self._settings)

