"""Stage 1/2 산출물 타입드 로더 — universe (name + market) + quality-pass.

구 ``catalyst_scan._load_universe_tickers`` / ``_load_quality_pass`` +
``stage3_earnings_panic._load_universe_market`` 의 단일화. 경로는 ``_boundary``
경유 (``$TRAIL_TODAY``).
"""
from __future__ import annotations

import json

from domains.catalyst import _boundary


def load_universe_tickers(date: str) -> tuple[dict[str, str], list[str]]:
    """01-universe.json → {ticker: name} dict. 누락 시 warning."""
    p = _boundary.resolve_trail_dir(date) / "01-universe.json"
    if not p.exists():
        return {}, [f"universe 파일 미존재: {p}"]
    with p.open("r", encoding="utf-8") as f:
        data = json.load(f)
    out: dict[str, str] = {}
    for e in data.get("entries") or []:
        t = e.get("ticker")
        if t and t not in out:
            out[t] = e.get("name", t)
    return out, []


def load_universe_market(date: str) -> dict[str, str]:
    """01-universe.json → {stock_code: market} (KR: ticker 만, metadata.market, 기본 KOSPI)."""
    p = _boundary.resolve_trail_dir(date) / "01-universe.json"
    if not p.exists():
        return {}
    with p.open("r", encoding="utf-8") as f:
        data = json.load(f)
    out: dict[str, str] = {}
    for e in data.get("entries") or []:
        t = e.get("ticker", "")
        if not t.startswith("KR:"):
            continue
        code = t.split(":", 1)[1]
        if len(code) != 6:
            continue
        market = (e.get("metadata") or {}).get("market") or "KOSPI"
        out[code] = market
    return out


def load_quality_pass(date: str) -> tuple[set[str], list[str]]:
    """02-quality-filter.json → quality 'pass' verdict ticker set (exact-match).

    'pass' 만 통과 — 'fail'/'unknown'/'caution' 은 모두 제외 (fail-safe).
    """
    p = _boundary.resolve_trail_dir(date) / "02-quality-filter.json"
    if not p.exists():
        return set(), [
            f"quality-filter 파일 미존재: {p} — quality 통과 confirm 불가, "
            "Stage 2 skip하고 universe 전체 대상으로 진행 (Stage 4 thesis-auditor가 추가 검증)"
        ]
    with p.open("r", encoding="utf-8") as f:
        data = json.load(f)
    out: set[str] = set()
    for v in data.get("verdicts") or []:
        if v.get("verdict") == "pass":
            t = v.get("ticker")
            if t:
                out.add(t)
    return out, []
