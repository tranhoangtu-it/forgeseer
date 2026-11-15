from forgeseer.advisor import GradeOddsTable, SwordOdds
from forgeseer.app import sim_source
from forgeseer.charts import scale, tick_step
from forgeseer.simulator import SimReport, StrategyResult
from forgeseer.sim_tab import SimSource, report_lines, source_line
from tests.test_simulator import _state


def _result(key, win, day, runs=500) -> StrategyResult:
    return StrategyResult(key=key, runs=runs, survival=(1.0, 0.5, win), first_day=22, win=win,
                          expected_day=day)


def test_report_lines_put_best_strategy_first():
    report = SimReport(results=(_result("advisor", 0.125, 23.4), _result("safe_only", 0.0, 22.1)),
                       seconds=0.84, assumed=False)

    assert report_lines(report) == [
        "Nên chơi: Theo overlay (12,5% qua hết lượt)",
        "Theo overlay: qua hết lượt 12,5% · trung bình tới ngày 23,4",
        "Chỉ đập an toàn: qua hết lượt 0,0% · trung bình tới ngày 22,1",
        "500 lượt mỗi cách · 0,8 giây",
    ]


def test_source_line():
    assert source_line(SimSource(None, live=True, day=7)) == "Dữ liệu: đọc trực tiếp từ game, ngày 7."
    assert source_line(SimSource(None, live=False, day=7)) == "Dữ liệu: file save, ngày 7."


class _FakeLive:
    def odds(self):
        return {}, 1.5

    def quota(self):
        return 29500.0

    def quota_schedule(self):
        return (44200.0,)

    def grade_odds(self):
        odds = SwordOdds(0.0, 0.0, 0.3, 0.6, 0.1)
        return GradeOddsTable(normal={0: odds}, fever={0: odds}, valid=True)


def test_sim_source_uses_live_numbers_when_live():
    source = sim_source(_state(), _FakeLive(), fever_strikes=6)

    assert source.live and source.day == 10
    assert source.inp.need_today == 29500 - 5000 and not source.inp.assumed
    assert source.inp.fever_strikes == 6


def test_sim_source_from_save_only():
    source = sim_source(_state(), None, fever_strikes=7)

    assert not source.live and source.inp.assumed
    assert sim_source(None, None, 7) is None
    assert sim_source(_state(finished=True), None, 7).inp is None


def test_chart_helpers():
    assert scale(5, 0, 10, 0, 100) == 50
    assert scale(1, 1, 1, 0, 100) == 50
    assert tick_step(24) == 3 and tick_step(5) == 1
