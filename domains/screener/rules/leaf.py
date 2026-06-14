"""Leaf Rule — Threshold / Scoring / SignalPresence 3종.

leaf 는 metric_path 1개 또는 signal set 1개를 평가. composite (And/Or/Not/
WeightedSum) 가 leaf 여러 개를 묶음.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping

from domains.screener.domain.ticker import TickerSnapshot
from domains.screener.domain.verdict import RuleResult
from domains.screener.errors import InsufficientHistoryError, MetricResolutionError
from domains.screener.rules.base import Rule
from domains.screener.rules.methods import apply_method
from domains.screener.rules.resolver import resolve_metric

# ThresholdRule 이 지원하는 비교 op 의 SSoT. selector(attributes.NUMERIC_OPS)와 달리
# ``ne`` 는 미지원 — cutoff 는 floor/ceiling 의미라 != 가 무의미. methods_manifest.yaml
# 생성기 + 정책 strict validator 가 본 상수를 읽어 op 화이트리스트로 쓴다.
THRESHOLD_OPS: frozenset[str] = frozenset({"ge", "le", "gt", "lt", "eq"})


@dataclass(frozen=True)
class ThresholdRule(Rule):
    """Hard floor / Hard ceiling — binary pass/fail."""

    _name: str
    metric_path: str
    op: str
    threshold: float
    period_years: int | None = None
    tax_rate: float | None = None

    @property
    def name(self) -> str:
        return self._name

    def evaluate(self, snapshot: TickerSnapshot) -> RuleResult:
        try:
            value = resolve_metric(
                snapshot,
                self.metric_path,
                period_years=self.period_years,
                tax_rate=self.tax_rate,
            )
        except (InsufficientHistoryError, MetricResolutionError) as e:
            return RuleResult(
                rule_name=self._name,
                passed=False,
                score=0.0,
                reasons=(f"data_missing: {e}",),
                children=(),
                citations=snapshot.all_citations(),
            )

        ops = {
            "ge": value >= self.threshold,
            "le": value <= self.threshold,
            "gt": value > self.threshold,
            "lt": value < self.threshold,
            "eq": value == self.threshold,
        }
        if self.op not in ops:
            raise ValueError(f"unknown threshold op: {self.op}")
        passed = ops[self.op]
        reasons = (
            ()
            if passed
            else (f"{self.metric_path}={value:.4f} {self.op} {self.threshold}",)
        )
        return RuleResult(
            rule_name=self._name,
            passed=passed,
            score=1.0 if passed else 0.0,
            reasons=reasons,
            children=(),
            citations=snapshot.all_citations(),
        )


@dataclass(frozen=True)
class ScoringRule(Rule):
    """registered scoring method 적용. score ≥ pass_score 면 pass.

    params 는 ``MappingProxyType`` 으로 자동 변환되어 frozen 보장 + hashable.
    factory 는 dict 를 넘기지만 __post_init__ 이 read-only mapping 으로 wrap.
    """

    _name: str
    metric_path: str
    method: str
    params: Mapping[str, Any] = field(default_factory=dict)
    pass_score: float = 0.5
    period_years: int | None = None
    tax_rate: float | None = None

    def __post_init__(self) -> None:
        # dict → MappingProxyType. caller 가 mutation 시도해도 TypeError.
        if not isinstance(self.params, MappingProxyType):
            object.__setattr__(
                self, "params", MappingProxyType(dict(self.params))
            )

    @property
    def name(self) -> str:
        return self._name

    def evaluate(self, snapshot: TickerSnapshot) -> RuleResult:
        try:
            value = resolve_metric(
                snapshot,
                self.metric_path,
                period_years=self.period_years,
                tax_rate=self.tax_rate,
            )
        except (InsufficientHistoryError, MetricResolutionError) as e:
            return RuleResult(
                rule_name=self._name,
                passed=False,
                score=0.0,
                reasons=(f"data_missing: {e}",),
                children=(),
                citations=snapshot.all_citations(),
            )

        score = apply_method(self.method, value, **self.params)
        passed = score >= self.pass_score
        reasons = (
            ()
            if passed
            else (
                f"{self.metric_path}={value:.4f}, score={score:.3f} < {self.pass_score}",
            )
        )
        return RuleResult(
            rule_name=self._name,
            passed=passed,
            score=score,
            reasons=reasons,
            children=(),
            citations=snapshot.all_citations(),
        )


@dataclass(frozen=True)
class SignalPresenceRule(Rule):
    """capital_allocation_signals 같은 set membership 검사."""

    _name: str
    required_any_of: tuple[str, ...]

    @property
    def name(self) -> str:
        return self._name

    def evaluate(self, snapshot: TickerSnapshot) -> RuleResult:
        signals = set(snapshot.capital_allocation_signals)
        required = set(self.required_any_of)
        match = signals & required
        passed = bool(match)
        reasons = (
            ()
            if passed
            else (f"none of {sorted(required)} in {sorted(signals)}",)
        )
        return RuleResult(
            rule_name=self._name,
            passed=passed,
            score=1.0 if passed else 0.0,
            reasons=reasons,
            children=(),
            citations=snapshot.all_citations(),
        )
