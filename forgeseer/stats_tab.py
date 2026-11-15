"""The "Stats" tab: runs played, best/average day, where lost runs ended, highest grade trend.

Reads runs.jsonl and days.jsonl each time the tab is built (both are small).
"""
from __future__ import annotations

from pathlib import Path
from tkinter import ttk

from .charts import bar_chart, line_chart, make_canvas
from .day_log import DEFAULT_DAY_LOG, load_days
from .i18n import t
from .run_log import DEFAULT_RUN_LOG, load_runs
from .stats import RunStats, run_stats
from .text_format import fmt_dec, fmt_int

WRAP_PX = 430
CHART_HEIGHT = 140


def summary_lines(stats: RunStats | None) -> list[str]:
    if stats is None:
        return [t("stats.empty")]
    lines = [t("stats.summary", runs=fmt_int(stats.runs), wins=fmt_int(stats.wins),
               best=stats.best_day, avg=fmt_dec(stats.avg_day, 1))]
    if stats.first_miss_avg is not None:
        lines.append(t("stats.first_miss", day=fmt_dec(stats.first_miss_avg, 1),
                       runs=fmt_int(stats.first_miss_runs)))
    return lines


class StatsTab:
    def __init__(self, runs_path: Path = DEFAULT_RUN_LOG, days_path: Path = DEFAULT_DAY_LOG) -> None:
        self.runs_path = runs_path
        self.days_path = days_path

    def stats(self) -> RunStats | None:
        return run_stats(load_runs(self.runs_path), load_days(self.days_path))

    def build(self, parent: ttk.Notebook) -> ttk.Frame:
        frame = ttk.Frame(parent, padding=10)
        stats = self.stats()
        ttk.Label(frame, text="\n".join(summary_lines(stats)), wraplength=WRAP_PX,
                  justify="left").pack(anchor="w")
        if stats is None:
            return frame
        ends = make_canvas(frame, height=CHART_HEIGHT)
        ends.pack(anchor="w", pady=(8, 0))
        if stats.end_days:
            bar_chart(ends, [(str(day), count) for day, count in stats.end_days],
                      title=t("stats.end_days"))
        else:
            ends.create_text(10, 10, text=t("stats.no_losses"), anchor="nw")
        trend = make_canvas(frame, height=CHART_HEIGHT)
        trend.pack(anchor="w", pady=(8, 0))
        grades = stats.grade_trend
        line_chart(trend, list(range(1, len(grades) + 1)), [("", [float(g) for g in grades])],
                   float(max(max(grades), 1)), lambda v: f"+{v:.0f}", title=t("stats.grades"))
        return frame
