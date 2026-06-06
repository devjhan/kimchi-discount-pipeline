"""Shadow portfolio 순수 규칙 (I/O 無, 결정론).

구 LLM 스킬 산문이 매일 손으로 수행하던 판단을 재현가능한 함수로 회수한다 (F-6).
tier 선정 / 보유 만료 / 분기 경계 / random seed 모두 deterministic.
"""
from __future__ import annotations

import hashlib
from datetime import date as _date
from typing import Any, Iterable

_PRIMARY_TRIGGER = ("a_type", "b_type")


def quarter_of(date_iso: str) -> str:
    """``YYYY-MM-DD`` → ``YYYY-Qn`` (1=Jan-Mar … 4=Oct-Dec)."""
    d = _date.fromisoformat(date_iso)
    return f"{d.year}-Q{(d.month - 1) // 3 + 1}"


def holding_age_days(entry_date: str, today: str) -> int:
    """entry_date → today 경과 일수 (음수 방지 0 floor)."""
    if not entry_date:
        return 0
    delta = (_date.fromisoformat(today) - _date.fromisoformat(entry_date)).days
    return max(0, delta)


def select_top_k_catalyst_tickers(catalysts: Iterable[dict[str, Any]], k: int) -> list[str]:
    """tier_1 mechanical 선정 — primary(a/b) catalyst ticker 를 03 산출 순서대로 dedup 후 top-K.

    명시적 numeric score 가 catalyst event 에 없으므로 *결정론적 출력 순서* (detector
    실행 순서 → ticker) 를 'mechanical' 순위로 사용한다 (LLM 판단 0).
    """
    out: list[str] = []
    seen: set[str] = set()
    for c in catalysts:
        if c.get("trigger_class") not in _PRIMARY_TRIGGER:
            continue
        t = c.get("ticker")
        if not t or t in seen:
            continue
        seen.add(t)
        out.append(t)
        if len(out) >= k:
            break
    return out


def deterministic_random_k(pool: Iterable[str], k: int, date_iso: str) -> list[str]:
    """tier_3 random 선정 — date hash seed 로 재현가능한 K 선택 (정렬 출력).

    seed = sha256(date) 상위 8바이트. 같은 (pool, date) → 같은 결과.
    """
    import random as _random

    items = sorted(set(pool))
    if k <= 0 or not items:
        return []
    seed = int.from_bytes(hashlib.sha256(date_iso.encode("utf-8")).digest()[:8], "big")
    rng = _random.Random(seed)
    chosen = rng.sample(items, min(k, len(items)))
    return sorted(chosen)


def max_weight_drift(weights: Iterable[float], target: float) -> float:
    """현재 weight 들의 target 대비 최대 절대 편차 (tier_0 rebalance 판정용)."""
    ws = list(weights)
    if not ws:
        return 0.0
    return max(abs(w - target) for w in ws)


def trade_return_pct(entry_price: float, exit_price: float) -> float:
    """청산 수익률 = exit/entry - 1 (entry<=0 이면 0.0)."""
    if entry_price <= 0:
        return 0.0
    return round(exit_price / entry_price - 1.0, 6)
