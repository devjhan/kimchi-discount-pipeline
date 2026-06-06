"""Stage 5d thesis-expiry 의 순수 도메인 규칙 — value object + tier 분류.

F-8: 절차적으로 thesis_expiry_monitor.py 에 박혀 있던 순수 규칙 (4-tier 만료 분류 /
value object / 월→일 환산 상수) 회수. 본 모듈은 **순수** — IO / `_boundary` 접근 0.
compute_expiry (citation 조립 / KST date 파싱) 와 IO 는 ``application/thesis_expiry.py``.
"""
from __future__ import annotations

from dataclasses import dataclass, field

DEFAULT_TIERS = {
    "notice_days":  90,
    "warn_days":    30,
    "expired_days":  0,
    "overdue_days": -30,
}

# 30.4375 일 = 1 month (falsifier_proximity 와 동일 산식)
DAYS_PER_MONTH = 30.4375


@dataclass
class ExpiryRecord:
    ticker: str
    name: str
    entry_date: str
    horizon_months: float
    expiry_date: str
    days_remaining: int
    tier: str  # 'notice' | 'warn' | 'expired' | 'overdue' | 'unmeasurable'
    rationale: str
    needs_user_decision: bool
    citations: list[str] = field(default_factory=list)


def classify_tier(days_remaining: int, tiers: dict[str, int]) -> str:
    """days_remaining (양수 = 미래, 음수 = 과거) → tier."""
    if days_remaining < tiers["overdue_days"]:
        # 30+ 일 이상 지남 — 여전히 overdue
        return "overdue"
    if days_remaining < tiers["expired_days"]:
        # -30 < x < 0 — overdue
        return "overdue"
    if days_remaining == tiers["expired_days"]:
        return "expired"
    if days_remaining <= tiers["warn_days"]:
        return "warn"
    if days_remaining <= tiers["notice_days"]:
        return "notice"
    return "ok"  # > notice_days — far from expiry
