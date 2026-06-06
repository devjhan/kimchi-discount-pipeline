"""Stage 5b falsifier-proximity 의 순수 도메인 규칙 — value object + 분류 산수.

F-8: 절차적으로 falsifier_proximity.py 에 박혀 있던 순수 규칙 (proximity band 분류 /
경과 개월 산수 / value object) 회수. 본 모듈은 **순수** — IO / `_boundary` / 파일 접근 0.
measurement orchestration (citation 조립 / category dispatch / market_snapshot) 은
``application/falsifier_proximity.py`` 책임.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta

# KST — _months_between 의 tz 부여용 (utils.KST 와 동일 정의; domain 순수 유지 위해 로컬).
_KST = timezone(timedelta(hours=9))

DEFAULT_PROXIMITY_BANDS = {
    "low_max": 0.5,
    "medium_max": 0.9,
}


@dataclass
class ProximityRecord:
    ticker: str
    name: str
    proximity: str  # 'low' | 'medium' | 'high' | 'unmeasurable'
    distance_ratio: float | None  # 0.0 = falsifier 발동, 1.0 = entry 시점
    rationale: str
    falsifier_category: str
    citations: list[str] = field(default_factory=list)
    needs_user_decision: bool = False


def classify(distance_ratio: float | None, bands: dict[str, float]) -> str:
    """distance_ratio (0=발동, 1=entry) → low/medium/high/unmeasurable."""
    if distance_ratio is None:
        return "unmeasurable"
    inverse = max(0.0, min(1.0, 1.0 - distance_ratio))  # 0=entry, 1=발동
    if inverse < bands["low_max"]:
        return "low"
    if inverse < bands["medium_max"]:
        return "medium"
    return "high"


def months_between(start: str, end: str) -> float:
    """KST 기준 소수점 개월 수. 30.4375 일 = 1 month."""
    s = datetime.strptime(start, "%Y-%m-%d").replace(tzinfo=_KST)
    e = datetime.strptime(end, "%Y-%m-%d").replace(tzinfo=_KST)
    days = (e - s).total_seconds() / 86400.0
    return round(days / 30.4375, 4)
