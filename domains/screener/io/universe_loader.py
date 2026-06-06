"""Universe loader — ``$TRAIL_TODAY/01-universe.json`` 의 entries 를 ingest.

외부 시스템 (Stage 1 산출) 의 raw JSON 을 screener domain 객체로 변환.
ticker 단위 dedup 은 입력 측 책임이 아니라 본 loader 의 책임 (anti-corruption).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Mapping

from domains.screener import _boundary
from domains._shared.time.clock import AsOfClock


@dataclass(frozen=True)
class UniverseEntry:
    """단일 universe 항목 — Stage 1 entries[] 의 1 element."""

    ticker: str
    name: str
    source_citation: str
    enrichments: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    """Stage 1 EnrichedEntry.enrichments — {group: {key: value}}. 미보강 종목은 빈 dict."""


def load_universe(
    clock: AsOfClock,
) -> tuple[tuple[UniverseEntry, ...], tuple[str, ...]]:
    """clock.trading_date 기준 universe 로드. ``(entries, warnings)`` 반환.

    파일 부재 / 파싱 실패 시 빈 entries + warning. raise 하지 않음 (downstream
    이 empty universe 를 정상 처리하도록).
    """
    date_iso = clock.trading_date.isoformat()
    universe_path = _boundary.resolve_path("trail_today", date=date_iso) / "01-universe.json"

    if not universe_path.exists():
        return (), (f"universe 파일 미존재: {universe_path}",)

    try:
        with universe_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return (), (f"universe 파일 파싱 실패: {e}",)

    raw_entries = data.get("entries") or []
    seen: set[str] = set()
    entries: list[UniverseEntry] = []
    for raw in raw_entries:
        ticker = raw.get("ticker")
        if not ticker or ticker in seen:
            continue
        seen.add(ticker)
        entries.append(
            UniverseEntry(
                ticker=ticker,
                name=raw.get("name", ticker),
                source_citation=raw.get("source_citation", ""),
                enrichments=raw.get("enrichments") or {},
            )
        )
    return tuple(entries), ()
