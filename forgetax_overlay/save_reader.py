"""Tìm và phân tích file save lượt chơi của ForgeTax.

File save có dạng ``{"version": int, "payload": "<chuỗi JSON>", "checksum": str}``.
Module này chỉ ĐỌC file; không bao giờ ghi để tránh làm hỏng checksum của game.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_SAVE_DIR = (
    Path(os.environ.get("USERPROFILE", str(Path.home())))
    / "AppData" / "LocalLow" / "DefaultCompany" / "ForgeTax" / "Save"
)
# Tên file lượt chơi đổi theo bản phát hành (vd. run_release24_v1_1.json).
RUN_SAVE_GLOB = "run_release*_v*.json"
# Mã vị trí kiếm (GPT6Sword.place) suy ra từ dữ liệu game:
# 0 = trên sàn, 3 = trên đe, 4 = trên giá (kèm ô rack), 5 = trên bàn cống nạp (đã nộp).
PLACE_FLOOR = 0
PLACE_ANVIL = 3
PLACE_RACK = 4
PLACE_TRIBUTE = 5


class SaveReadError(Exception):
    """File save không đọc được (đang ghi dở, sai định dạng, ...)."""


@dataclass(frozen=True)
class Relic:
    id: str
    rank: int


@dataclass(frozen=True)
class Offer:
    id: str
    price: int
    sold: bool


@dataclass(frozen=True)
class MerchantOffer:
    """Hàng của Thương nhân ma (kiếm hoặc vật phẩm tiêu hao), giá bằng vàng."""
    id: str
    price: float
    sold: bool
    grade: int
    stock: int
    purchases: int


@dataclass(frozen=True)
class Sword:
    serial: int
    grade: int
    value: int
    peak: int
    strikes: int
    success_streak: int
    normal_hits: int
    normal_successes: int
    heated: bool
    broken: bool
    active: bool
    rack: int
    damage_count: int
    fever_remaining: float
    charge: int = 0  # tích lực Xuất Thần (đủ ngưỡng -> nhát kế tiếp vào Xuất Thần)
    place: int = PLACE_FLOOR  # mã vị trí trong lò rèn (xem PLACE_*)

    @property
    def where(self) -> str:
        """Vị trí nhìn thấy được trong game (serial nội bộ không hiện trong game)."""
        if self.place == PLACE_RACK and self.rack >= 0:
            return f"giá ô {self.rack + 1}"
        if self.place == PLACE_FLOOR:
            return "dưới sàn"
        if self.place == PLACE_ANVIL:
            return "trên đe"
        if self.place == PLACE_TRIBUTE:
            return "bàn cống"
        return "đang cầm"  # các mã còn lại: trên tay / trong lò

    @property
    def tag(self) -> str:
        """Tên ngắn để nhận ra kiếm trong game: cấp '+N' như game hiển thị + vị trí."""
        return f"+{self.grade} {self.where}"

    @property
    def success_rate(self) -> float | None:
        """Tỉ lệ nhát đập thường thành công thực tế; None nếu chưa đập nhát nào."""
        if self.normal_hits <= 0:
            return None
        return self.normal_successes / self.normal_hits

    @property
    def is_live(self) -> bool:
        """Kiếm còn trong tay (chưa gãy, chưa đặt lên bàn cống nạp)."""
        return self.active and not self.broken and self.place != PLACE_TRIBUTE


@dataclass(frozen=True)
class RunState:
    active: bool
    round: int
    deadline_round: int
    wallet: int
    pending_tribute: int
    successful_tributes: int
    missed_tributes: int
    ward_charges: int
    sword_credits: int
    rerolls: int
    rewind_charges: int
    shopping: bool
    finished: bool
    won: bool
    broken_swords: int
    great_events: int
    hold_events: int
    damage_events: int
    fever_events: int
    gold_earned: int
    highest_grade: int
    play_seconds: float
    relics: tuple[Relic, ...]
    offers: tuple[Offer, ...]
    swords: tuple[Sword, ...]
    consumables: int
    delivered: int = 0  # giá trị kiếm đã cống nạp trong vòng hiện tại
    merchant_offers: tuple[MerchantOffer, ...] = ()
    merchant_round: int = 0  # vòng thương nhân đang ghé (== round -> đang có mặt)
    run_id: str = ""  # campaign.anonymousRunId (định danh lượt chơi)


def find_run_save(save_dir: Path = DEFAULT_SAVE_DIR) -> Path | None:
    """Trả về file save lượt chơi mới nhất; bỏ qua bản sao lưu ``*.previous``."""
    if not save_dir.is_dir():
        return None
    candidates = [p for p in save_dir.glob(RUN_SAVE_GLOB) if p.is_file()]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime_ns)


def load_run_state(path: Path) -> RunState:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:  # file bị khóa / vừa bị thay thế khi game ghi
        raise SaveReadError(f"Không đọc được {path.name}: {exc}") from exc
    return parse_run_save(text)


def parse_run_save(text: str) -> RunState:
    try:
        outer = json.loads(text)
        payload = json.loads(outer["payload"])
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise SaveReadError(f"File save sai định dạng: {exc}") from exc
    if not isinstance(payload, dict):
        raise SaveReadError("Payload không phải object JSON")
    return _build_state(payload)


def _int(d: dict[str, Any], key: str) -> int:
    return int(_float(d, key))


def _float(d: dict[str, Any], key: str) -> float:
    value = d.get(key, 0)
    return float(value) if isinstance(value, (int, float)) else 0.0


def _bool(d: dict[str, Any], key: str) -> bool:
    return bool(d.get(key, False))


def _dict(d: dict[str, Any], key: str) -> dict[str, Any]:
    value = d.get(key)
    return value if isinstance(value, dict) else {}


def _list(d: dict[str, Any], key: str) -> list[Any]:
    value = d.get(key)
    return [v for v in value if isinstance(v, dict)] if isinstance(value, list) else []


def _build_sword(raw: dict[str, Any]) -> Sword:
    fx = _dict(raw, "effects")
    return Sword(
        serial=_int(raw, "serial"),
        grade=_int(raw, "grade"),
        value=_int(raw, "value"),
        peak=_int(fx, "peak"),
        strikes=_int(raw, "strikes"),
        success_streak=_int(fx, "successStreak"),
        normal_hits=_int(fx, "normalHits"),
        normal_successes=_int(fx, "normalSuccesses"),
        heated=_bool(raw, "heated"),
        broken=_bool(raw, "broken"),
        active=_bool(raw, "active"),
        rack=_int(raw, "rack"),
        damage_count=_int(fx, "damageCount"),
        fever_remaining=_float(raw, "feverRemaining"),
        charge=_int(fx, "charge"),
        place=_int(raw, "place"),
    )


def _build_state(payload: dict[str, Any]) -> RunState:
    camp = _dict(payload, "campaign")
    record = _dict(camp, "Record")
    consumables = camp.get("consumables")
    return RunState(
        active=_bool(payload, "active"),
        round=_int(camp, "round"),
        deadline_round=_int(camp, "contractDeadlineRound"),
        wallet=_int(camp, "wallet"),
        pending_tribute=_int(camp, "pendingTribute"),
        successful_tributes=_int(camp, "successfulTributes"),
        missed_tributes=_int(camp, "missedTributes"),
        ward_charges=_int(camp, "wardCharges"),
        sword_credits=_int(camp, "swordCredits"),
        rerolls=_int(camp, "rerolls"),
        rewind_charges=_int(camp, "rewindCharges"),
        shopping=_bool(camp, "shopping"),
        finished=_bool(camp, "finished"),
        won=_bool(camp, "won"),
        broken_swords=_int(camp, "brokenSwords"),
        great_events=_int(camp, "greatEvents"),
        hold_events=_int(camp, "holdEvents"),
        damage_events=_int(camp, "damageEvents"),
        fever_events=_int(camp, "feverEvents"),
        gold_earned=_int(record, "goldEarned"),
        highest_grade=_int(record, "highestGrade"),
        play_seconds=_float(record, "seconds"),
        relics=tuple(
            Relic(str(r.get("id", "")), _int(r, "rank"))
            for r in _list(camp, "relics") if r.get("id")
        ),
        offers=tuple(
            Offer(str(o.get("id", "")), _int(o, "price"), _bool(o, "sold"))
            for o in _list(camp, "offers") if o.get("id")
        ),
        swords=tuple(_build_sword(s) for s in _list(payload, "swords")),
        consumables=len(consumables) if isinstance(consumables, list) else 0,
        delivered=_int(payload, "delivered"),
        merchant_offers=tuple(
            MerchantOffer(str(o.get("id", "")), _float(o, "price"), _bool(o, "sold"),
                          _int(o, "grade"), _int(o, "stock"), _int(o, "purchases"))
            for o in _list(camp, "merchantOffers") if o.get("id")
        ),
        merchant_round=_int(camp, "merchantRound"),
        run_id=str(camp.get("anonymousRunId") or ""),
    )
