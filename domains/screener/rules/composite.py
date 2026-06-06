"""Composite Rule — And / Or / Not / WeightedSum.

leaf 여러 개를 묶어 boolean / weighted score 트리 구성. children 은 frozen
tuple — 평가 결과는 children 의 RuleResult 를 그대로 보관.
"""
from __future__ import annotations

from dataclasses import dataclass

from domains.screener.domain.ticker import TickerSnapshot
from domains.screener.domain.verdict import RuleResult
from domains.screener.rules.base import Rule


@dataclass(frozen=True)
class AndRule(Rule):
    """모든 children 이 pass 일 때 pass. score = min."""

    _name: str
    children: tuple[Rule, ...]

    @property
    def name(self) -> str:
        return self._name

    def evaluate(self, snapshot: TickerSnapshot) -> RuleResult:
        results = tuple(c.evaluate(snapshot) for c in self.children)
        passed = all(r.passed for r in results)
        score = min((r.score for r in results), default=0.0)
        reasons = tuple(
            f"{r.rule_name}: {reason}"
            for r in results
            if not r.passed
            for reason in (r.reasons or (f"score={r.score:.2f}",))
        )
        citations = tuple({c for r in results for c in r.citations})
        return RuleResult(
            rule_name=self._name,
            passed=passed,
            score=score,
            reasons=reasons,
            children=results,
            citations=citations,
        )


@dataclass(frozen=True)
class OrRule(Rule):
    """하나라도 pass 면 pass. score = max."""

    _name: str
    children: tuple[Rule, ...]

    @property
    def name(self) -> str:
        return self._name

    def evaluate(self, snapshot: TickerSnapshot) -> RuleResult:
        results = tuple(c.evaluate(snapshot) for c in self.children)
        passed = any(r.passed for r in results)
        score = max((r.score for r in results), default=0.0)
        reasons = (
            ()
            if passed
            else tuple(
                f"{r.rule_name}: {reason}"
                for r in results
                for reason in r.reasons
            )
        )
        citations = tuple({c for r in results for c in r.citations})
        return RuleResult(
            rule_name=self._name,
            passed=passed,
            score=score,
            reasons=reasons,
            children=results,
            citations=citations,
        )


@dataclass(frozen=True)
class NotRule(Rule):
    """inner 의 결과 반전. score = 1 - inner.score."""

    _name: str
    inner: Rule

    @property
    def name(self) -> str:
        return self._name

    def evaluate(self, snapshot: TickerSnapshot) -> RuleResult:
        r = self.inner.evaluate(snapshot)
        return RuleResult(
            rule_name=self._name,
            passed=not r.passed,
            score=1.0 - r.score,
            reasons=(f"NOT {r.rule_name}",) if r.passed else (),
            children=(r,),
            citations=r.citations,
        )


@dataclass(frozen=True)
class WeightedSumRule(Rule):
    """children 의 weighted average score. pass_score 이상이면 pass."""

    _name: str
    children: tuple[tuple[Rule, float], ...]
    pass_score: float

    @property
    def name(self) -> str:
        return self._name

    def evaluate(self, snapshot: TickerSnapshot) -> RuleResult:
        results = tuple((c.evaluate(snapshot), w) for c, w in self.children)
        total_w = sum(w for _, w in results)
        if total_w <= 0:
            raise ValueError(f"{self._name}: total weight 가 양수가 아님")
        weighted = sum(r.score * w for r, w in results) / total_w
        passed = weighted >= self.pass_score
        reasons = (
            ()
            if passed
            else (f"weighted_score={weighted:.3f} < pass_score={self.pass_score}",)
        )
        citations = tuple({c for r, _ in results for c in r.citations})
        return RuleResult(
            rule_name=self._name,
            passed=passed,
            score=weighted,
            reasons=reasons,
            children=tuple(r for r, _ in results),
            citations=citations,
        )
