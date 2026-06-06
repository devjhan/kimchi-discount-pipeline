"""RuleResult / ScreenVerdict — Rule 평가 결과 객체.

frozen + tuple 으로 immutable. JSON 직렬화는 caller 가 ``dataclasses.asdict``
로 변환 후 ``write_envelope`` 에 전달.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Verdict = Literal["pass", "fail", "caution", "unknown"]
# caution = "평가됐으나 정책상 필수 enrichment 누락 / 불량 프로파일 — fail-safe,
# 사람 재검토". unknown(데이터 전무, citation 면제)과 달리 실제 citations 보유 →
# citation 면제 아님.


@dataclass(frozen=True)
class RuleResult:
    """단일 Rule 평가의 결과. children 으로 트리 추적 가능."""

    rule_name: str
    passed: bool
    score: float
    reasons: tuple[str, ...] = field(default_factory=tuple)
    children: tuple["RuleResult", ...] = field(default_factory=tuple)
    citations: tuple[str, ...] = field(default_factory=tuple)

    @property
    def has_hard_floor_violation(self) -> bool:
        """reasons 중 ``HARD_FLOOR:`` prefix 가 하나라도 있으면 True."""
        return any(r.startswith("HARD_FLOOR:") for r in self.reasons)


@dataclass(frozen=True)
class ScreenVerdict:
    """단일 ticker 에 대한 최종 스크리닝 결과.

    Stage 3/4/6 / quality-lens / audit-shadow 가 read 하는 schema 의
    items 단일 element. verdict 가 ``unknown`` 이면 citations 면제
    (_shared/brief_gate/validators.py).
    """

    ticker: str
    name: str
    verdict: Verdict
    score: float
    reasons: tuple[str, ...]
    citations: tuple[str, ...]
    rule_tree: RuleResult | None = None
