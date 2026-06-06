"""Stage 산출물 타입드 로더 — 03 catalyst / 05 sizing / 05c falsifier / 01∩02 pool.

shadow portfolio 4-tier 의 일별 input. 경로는 ``_boundary`` 경유 ($TRAIL_TODAY).
"""
from __future__ import annotations

import json
from pathlib import Path

from domains.audit_integrity import _boundary

_PRIMARY = ("a_type", "b_type")
_SIZED_VERDICTS = ("size_recommended", "size_recommended_half_cap")


def _load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def load_catalysts(date: str) -> tuple[list[dict], list[str]]:
    """03-catalyst-events.json 의 catalysts list (없으면 [] + warning)."""
    p = _boundary.resolve_trail_dir(date) / "03-catalyst-events.json"
    data = _load_json(p)
    if data is None:
        return [], [f"tier_1: 03-catalyst-events.json 미존재/parse fail: {p.name}"]
    return list(data.get("catalysts") or []), []


def primary_catalyst_tickers(catalysts: list[dict]) -> frozenset[str]:
    """오늘 primary(a/b) catalyst 가 있는 ticker set (tier_1 '미갱신' 판정용)."""
    return frozenset(
        c["ticker"]
        for c in catalysts
        if c.get("trigger_class") in _PRIMARY and c.get("ticker")
    )


def load_sizing_recs(date: str) -> tuple[list[tuple[str, float]], list[str]]:
    """05-sizing-recommendation.json 의 size_recommended(+half_cap) (ticker, size_pct)."""
    p = _boundary.resolve_trail_dir(date) / "05-sizing-recommendation.json"
    data = _load_json(p)
    if data is None:
        return [], [f"tier_2: 05-sizing-recommendation.json 미존재/parse fail: {p.name}"]
    out: list[tuple[str, float]] = []
    for r in data.get("recommendations") or []:
        if r.get("verdict") not in _SIZED_VERDICTS:
            continue
        t = r.get("ticker")
        size = r.get("size_pct_of_portfolio")
        if t and size is not None:
            out.append((t, float(size)))
    return out, []


def load_falsifier_triggered(date: str) -> frozenset[str]:
    """05c event-trigger-status-{date}.json 의 signal=='triggered' ticker set."""
    p = _boundary.resolve_trail_dir(date) / f"event-trigger-status-{date}.json"
    data = _load_json(p)
    if data is None:
        return frozenset()
    return frozenset(
        r["ticker"]
        for r in data.get("records") or []
        if r.get("signal") == "triggered" and r.get("ticker")
    )


def load_universe_quality_pool(date: str) -> tuple[list[str], list[str]]:
    """tier_3 pool = 01-universe ∩ 02-quality(pass). 정렬 list."""
    warnings: list[str] = []
    trail = _boundary.resolve_trail_dir(date)
    uni = _load_json(trail / "01-universe.json")
    if uni is None:
        return [], ["tier_3: 01-universe.json 미존재 — random pool 비어있음"]
    universe = {e.get("ticker") for e in uni.get("entries") or [] if e.get("ticker")}

    qual = _load_json(trail / "02-quality-filter.json")
    if qual is None:
        warnings.append("tier_3: 02-quality-filter.json 미존재 — universe 전체를 pool 로 사용")
        return sorted(universe), warnings
    passed = {v.get("ticker") for v in qual.get("verdicts") or [] if v.get("verdict") == "pass"}
    return sorted(universe & passed), warnings
