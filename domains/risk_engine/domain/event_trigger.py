"""Stage 5c event-trigger 의 순수 도메인 — value object + Stage 3 index.

F-8: ``EventTriggerStatus`` value object + ticker→catalyst index (순수 lookup) 회수.
본 모듈은 **순수** — IO / `_boundary` 접근 0. cross-reference 판정 (evaluate_position,
citation 조립) 과 IO 는 ``application/event_falsifier_linker.py``.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class EventTriggerStatus:
    ticker: str
    name: str
    falsifier_description: str
    watch_catalyst_type: str | None
    direction: str                    # "presence" | "absence" | "unspecified"
    stage3_matches: list[dict[str, Any]]
    seen_today: bool | None           # None if watch_catalyst_type 미지정
    signal: str                       # "triggered" | "not_triggered" | "unspecified"
    rationale: str
    source_citations: list[str]       # G7
    needs_user_decision: bool


def build_stage3_index(
    all_catalysts: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """ticker → catalyst list index (순수 JSON lookup, G6)."""
    idx: dict[str, list[dict[str, Any]]] = {}
    for c in all_catalysts:
        t = c.get("ticker") or ""
        idx.setdefault(t, []).append(c)
    return idx
