"""ResearchOutput — PolicyEngine.analyze 의 순수 산출 (commit 전 후보)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class ResearchOutput:
    """LLM research 산출 — commit 전 검증 대상.

    ``cutoff_rules`` 는 screener Rule dict-tree 문법 (RuleFactory 소비 가능해야).
    ``citations`` 는 G7 evidence. policy 는 이 객체를 EnrichCutoffProfile 로 승격
    (commit.py) — drift gate + versioning 통과 후.
    """

    ticker: str
    required_enrichments: tuple[str, ...]
    cutoff_rules: Mapping[str, Any]
    citations: tuple[str, ...]
    rationale_ko: str
