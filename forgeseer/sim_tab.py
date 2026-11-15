"""The "Simulation" tab of the settings window.

The button takes the latest snapshot (live if the overlay has one, else the save file), runs the
Monte Carlo on a worker thread and polls for the result from the Tk thread (Tk isn't
thread-safe). The last result survives a rebuild of the window (language change).
"""
from __future__ import annotations

import threading
import tkinter as tk
from dataclasses import dataclass
from tkinter import ttk
from typing import Callable

from .charts import line_chart, make_canvas
from .i18n import t
from .simulator import DEFAULT_RUNS, SimInput, SimReport, simulate
from .text_format import fmt_dec, fmt_int, fmt_pct

POLL_MS = 100
WRAP_PX = 430


@dataclass(frozen=True)
class SimSource:
    """What the simulation starts from."""
    inp: SimInput | None      # None when the run is over
    live: bool                # read live from the game (else: save file)
    day: int


SourceProvider = Callable[[], SimSource | None]  # None: no data at all


def strategy_name(key: str) -> str:
    return t(f"sim.strategy.{key}")


def source_line(source: SimSource) -> str:
    return t("sim.source_live" if source.live else "sim.source_save", day=source.day)


def report_lines(report: SimReport) -> list[str]:
    """Best strategy first, then one row per strategy, then runs/time."""
    lines = []
    best = report.best
    if best is not None:
        lines.append(t("sim.best", name=strategy_name(best.key), win=fmt_pct(best.win, 1)))
    for r in report.results:
        lines.append(t("sim.row", name=strategy_name(r.key), win=fmt_pct(r.win, 1),
                       day=fmt_dec(r.expected_day, 1)))
    runs = min((r.runs for r in report.results), default=0)
    lines.append(t("sim.meta", runs=fmt_int(runs), seconds=fmt_dec(report.seconds, 1)))
    return lines


class SimTab:
    def __init__(self, root: tk.Misc, provider: SourceProvider,
                 run: Callable[[SimInput], SimReport] = simulate) -> None:
        self.root = root
        self._provider = provider
        self._run = run
        self._report: SimReport | None = None
        self._source: SimSource | None = None
        self._message = ""
        self._pending: dict[str, SimReport] | None = None
        self._widgets: dict[str, tk.Widget] = {}

    @property
    def report(self) -> SimReport | None:
        return self._report

    @property
    def busy(self) -> bool:
        return self._pending is not None

    def build(self, parent: ttk.Notebook) -> ttk.Frame:
        frame = ttk.Frame(parent, padding=10)
        ttk.Label(frame, text=t("sim.intro", runs=fmt_int(DEFAULT_RUNS)), wraplength=WRAP_PX,
                  justify="left").pack(anchor="w")
        button = ttk.Button(frame, text=t("sim.run"), command=self.start)
        button.pack(anchor="w", pady=(8, 4))
        status = ttk.Label(frame, wraplength=WRAP_PX, justify="left")
        status.pack(anchor="w")
        canvas = make_canvas(frame)
        canvas.pack(anchor="w", pady=6)
        result = ttk.Label(frame, wraplength=WRAP_PX, justify="left")
        result.pack(anchor="w")
        self._widgets = {"button": button, "status": status, "canvas": canvas, "result": result}
        self._render()
        return frame

    # ---------- running ----------
    def start(self) -> None:
        if self.busy:
            return
        source = self._provider()
        self._source, self._report = source, None
        if source is None or source.inp is None:
            self._message = t("sim.no_data") if source is None else t("sim.finished")
            self._render()
            return
        self._message = t("sim.running")
        box: dict[str, SimReport | None] = {}
        self._pending = box
        inp = source.inp

        def work() -> None:
            try:
                box["report"] = self._run(inp)
            except Exception:  # noqa: BLE001 - a bad snapshot must not leave the button stuck
                box["report"] = None
        threading.Thread(target=work, name="forgeseer-sim", daemon=True).start()
        self._render()
        self.root.after(POLL_MS, self._poll)

    def _poll(self) -> None:
        box = self._pending
        if box is None:
            return
        if "report" not in box:
            self.root.after(POLL_MS, self._poll)
            return
        report = box["report"]
        self._pending, self._report = None, report
        self._message = "" if report is not None else t("sim.no_data")
        self._render()

    # ---------- drawing ----------
    def _status_text(self) -> str:
        parts = [self._message] if self._message else []
        if self._source is not None and self._source.inp is not None:
            parts.insert(0, source_line(self._source))
            if self._source.inp.assumed:
                parts.append(t("sim.assumed"))
            parts.append(t("sim.assumptions", strikes=self._source.inp.fever_strikes))
        return "\n".join(parts)

    def _render(self) -> None:
        if not self._widgets or not self._widgets["status"].winfo_exists():
            return
        self._widgets["button"].configure(state="disabled" if self.busy else "normal")
        self._widgets["status"].configure(text=self._status_text())
        report = self._report
        self._widgets["result"].configure(text="\n".join(report_lines(report)) if report else "")
        canvas = self._widgets["canvas"]
        if report is None or not report.results:
            canvas.delete("all")
            return
        first = report.results[0]
        xs = list(range(first.first_day, first.first_day + len(first.survival)))
        line_chart(canvas, xs, [(strategy_name(r.key), r.survival) for r in report.results],
                   1.0, lambda v: fmt_pct(v, 0), title=t("sim.chart"))
