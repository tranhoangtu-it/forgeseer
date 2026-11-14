"""Đọc trạng thái lượt chơi TRỰC TIẾP từ game đang chạy qua Frida.

Một luồng nền tự gắn vào ForgeTax.exe (và gắn lại khi game khởi động lại), nạp
``live_capture.js``; script đó gửi JSON cùng định dạng payload của file save mỗi khi
trạng thái thay đổi (~300ms/lần). Không có Frida hoặc không gắn được -> overlay tự
quay về đọc file save.
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any, Callable

from .advisor import GradeOddsTable, PerSword, ShopSimulation, SwordOdds
from .relic_names import TEXTS_CACHE_FILE, RelicText, parse_relic_texts
from .save_reader import RunState, SaveReadError, parse_run_save

# serial kiếm -> (tỉ lệ bình thường, tỉ lệ khi đang fever)
OddsMap = dict[int, tuple[SwordOdds, SwordOdds]]
DEFAULT_MULTIPLIER = 1.5

PROCESS_NAME = "ForgeTax.exe"
SCRIPT_FILE = Path(__file__).with_name("live_capture.js")
RETRY_SECONDS = 3.0


class LiveSource:
    def __init__(self, process_name: str = PROCESS_NAME,
                 clock: Callable[[], float] = time.monotonic,
                 texts_cache: Path = TEXTS_CACHE_FILE) -> None:
        self.process_name = process_name
        self.texts_cache = texts_cache
        self._texts: dict[str, RelicText] = {}
        self.status = "Đọc trực tiếp: chưa kết nối"
        self._clock = clock
        self._lock = threading.Lock()
        self._state: RunState | None = None
        self._state_at: float | None = None
        self._odds: OddsMap = {}
        self._shop_sim = ShopSimulation()
        self._quota = 0.0
        self._next_quota = 0.0
        self._grade_odds = GradeOddsTable()
        self._multiplier = DEFAULT_MULTIPLIER
        self._session: Any = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    # ---------- dữ liệu (gọi từ luồng UI) ----------
    def latest(self) -> tuple[RunState | None, float | None]:
        """Trạng thái mới nhất và số giây kể từ lúc nhận; (None, None) nếu chưa có."""
        with self._lock:
            if self._state is None or self._state_at is None:
                return None, None
            return self._state, self._clock() - self._state_at

    def texts(self) -> dict[str, RelicText]:
        """Tên + mô tả relic chính thức đọc từ game (rỗng nếu chưa nhận)."""
        with self._lock:
            return self._texts

    def quota(self) -> float:
        """Cống phẩm phải nộp của vòng hiện tại (0 nếu chưa biết)."""
        with self._lock:
            return self._quota

    def next_quota(self) -> float:
        """Cống ngày mai do hàm của game tính trên campaign giả lập (0 nếu chưa xác minh được)."""
        with self._lock:
            return self._next_quota

    def grade_odds(self) -> GradeOddsTable:
        with self._lock:
            return self._grade_odds

    def shop_simulation(self) -> ShopSimulation:
        with self._lock:
            return self._shop_sim

    def odds(self) -> tuple[OddsMap, float]:
        """Tỉ lệ nhát kế tiếp của từng kiếm và hệ số giá trị mỗi grade."""
        with self._lock:
            return self._odds, self._multiplier

    # ---------- xử lý message từ script (luồng Frida) ----------
    def handle_message(self, message: dict[str, Any], _data: Any = None) -> None:
        if message.get("type") != "send":
            self.status = f"Đọc trực tiếp lỗi: {message.get('description', message)}"
            return
        payload = message.get("payload") or {}
        kind = payload.get("kind")
        if kind == "ready":
            self.status = "Đọc trực tiếp: đã kết nối"
        elif kind == "error":
            self.status = f"Đọc trực tiếp lỗi: {payload.get('message')}"
        elif kind == "run":
            self._accept_run(payload)
        elif kind == "texts":
            self._accept_texts(payload.get("items"))

    def _accept_texts(self, items: Any) -> None:
        texts = parse_relic_texts(items)
        if not texts:
            return
        with self._lock:
            self._texts = texts
        try:  # cache cho chế độ file save / lần mở sau khi chưa kết nối game
            self.texts_cache.parent.mkdir(parents=True, exist_ok=True)
            self.texts_cache.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass

    def _accept_run(self, payload: dict[str, Any]) -> None:
        wrapped = json.dumps({"version": 1, "payload": payload.get("json", ""), "checksum": ""})
        try:
            state = parse_run_save(wrapped)
        except SaveReadError:
            return  # giữ trạng thái cũ; bản chụp sau sẽ thay thế
        odds = _parse_odds(payload.get("odds"))
        multiplier = payload.get("multiplier")
        with self._lock:
            self._state, self._state_at = state, self._clock()
            self._odds = odds
            if "shopSim" in payload:  # chỉ gửi khi shop/relic/kiếm đổi -> giữ bản cũ nếu vắng
                self._shop_sim = _parse_shop_sim(payload["shopSim"])
            if "gradeOdds" in payload:
                self._grade_odds = _parse_grade_odds(payload["gradeOdds"])
            quota = payload.get("quota")
            if isinstance(quota, (int, float)):
                self._quota = float(quota)
            next_quota = payload.get("nextQuota")
            self._next_quota = float(next_quota) if isinstance(next_quota, (int, float)) else 0.0
            if isinstance(multiplier, (int, float)) and multiplier > 1:
                self._multiplier = float(multiplier)

    # ---------- vòng đời kết nối ----------
    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="forgetax-live", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        session, self._session = self._session, None
        if session is not None:
            try:
                session.detach()
            except Exception:  # noqa: BLE001 - game có thể đã tắt, detach lỗi là bình thường
                pass

    def _run(self) -> None:
        try:
            import frida  # import trễ: Frida là phụ thuộc tùy chọn
        except ImportError:
            self.status = "Đọc trực tiếp tắt: chưa cài frida (pip install frida)"
            return
        source = SCRIPT_FILE.read_text(encoding="utf-8")
        while not self._stop.is_set():
            if self._session is None:
                self._try_attach(frida, source)
            self._stop.wait(RETRY_SECONDS)

    def _try_attach(self, frida: Any, source: str) -> None:
        try:
            session = frida.attach(self.process_name)
            session.on("detached", self._on_detached)
            script = session.create_script(source)
            script.on("message", self.handle_message)
            script.load()
            self._session = session
        except frida.ProcessNotFoundError:
            self.status = "Đọc trực tiếp: chờ game mở..."
        except Exception as exc:  # noqa: BLE001 - mọi lỗi gắn đều chỉ làm overlay dùng file save
            self.status = f"Đọc trực tiếp lỗi: {exc}"

    def _on_detached(self, reason: str, *_: Any) -> None:
        self._session = None
        self.status = f"Đọc trực tiếp: mất kết nối ({reason})"


def _parse_odds(raw: Any) -> OddsMap:
    """``{"<serial>": {"normal": [5 số], "fever": [5 số]}}`` -> OddsMap; bỏ mục sai định dạng."""
    if not isinstance(raw, dict):
        return {}
    result: OddsMap = {}
    for serial, entry in raw.items():
        try:
            result[int(serial)] = (SwordOdds.from_permille(entry["normal"]),
                                   SwordOdds.from_permille(entry["fever"]))
        except (KeyError, TypeError, ValueError):
            continue
    return result


def _parse_per_sword(raw: Any) -> PerSword:
    """``{"<serial>": [5 số]}`` -> PerSword; bỏ mục sai định dạng."""
    if not isinstance(raw, dict):
        return {}
    parsed: PerSword = {}
    for serial, values in raw.items():
        try:
            parsed[int(serial)] = SwordOdds.from_permille(values)
        except (TypeError, ValueError):
            continue
    return parsed


def _parse_grade_odds(raw: Any) -> GradeOddsTable:
    if not isinstance(raw, dict):
        return GradeOddsTable()
    return GradeOddsTable(normal=_parse_per_sword(raw.get("normal")),
                          fever=_parse_per_sword(raw.get("fever")),
                          valid=bool(raw.get("valid")))


def _parse_by_id(raw: Any) -> dict[str, PerSword]:
    if not isinstance(raw, dict):
        return {}
    return {str(k): _parse_per_sword(v) for k, v in raw.items() if isinstance(v, dict)}


def _parse_shop_sim(raw: Any) -> ShopSimulation:
    """``{"buy": {id: per}, "drop": {id: per}, "swap": {offer: {relic: per}}}``."""
    if not isinstance(raw, dict):
        return ShopSimulation()
    swap_raw = raw.get("swap")
    swap = ({str(k): _parse_by_id(v) for k, v in swap_raw.items() if isinstance(v, dict)}
            if isinstance(swap_raw, dict) else {})
    grade = raw.get("grade") if isinstance(raw.get("grade"), dict) else {}
    grade_swap_raw = grade.get("swap")
    grade_swap = ({str(k): _parse_by_id(v) for k, v in grade_swap_raw.items() if isinstance(v, dict)}
                  if isinstance(grade_swap_raw, dict) else {})
    return ShopSimulation(buy=_parse_by_id(raw.get("buy")), drop=_parse_by_id(raw.get("drop")),
                          swap=swap, grade_base=_parse_per_sword(grade.get("base")),
                          grade_buy=_parse_by_id(grade.get("buy")), grade_swap=grade_swap)
