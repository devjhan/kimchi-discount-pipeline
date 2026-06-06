"""HardGuardWrapper — strategy tree 최상위에 factory 가 자동 삽입.

G13 enforcement: hard guards 중 하나라도 fail 이면 inner 무시하고 fail.
strategy YAML 이 직접 HardGuardWrapper 를 생성할 수 없음 (factory 에서만).
"""
from __future__ import annotations

from dataclasses import dataclass

from domains.screener.domain.ticker import TickerSnapshot
from domains.screener.domain.verdict import RuleResult
from domains.screener.rules.base import Rule


@dataclass(frozen=True)
class HardGuardWrapper(Rule):
    """outer wrapper — guards 가 fail 이면 inner 평가 생략하고 fail.

    reasons 에 ``HARD_FLOOR:`` prefix 를 붙여 downstream consumer (audit /
    brief) 가 hard floor 위반인지 즉시 식별 가능.
    """

    _name: str
    inner: Rule
    guards: tuple[Rule, ...]

    @property
    def name(self) -> str:
        return self._name

    def evaluate(self, snapshot: TickerSnapshot) -> RuleResult:
        guard_results = tuple(g.evaluate(snapshot) for g in self.guards)
        failed_guards = [r for r in guard_results if not r.passed]

        if failed_guards:
            reasons = tuple(
                f"HARD_FLOOR:{r.rule_name}: " + ", ".join(r.reasons)
                for r in failed_guards
            )
            citations = tuple({c for r in guard_results for c in r.citations})
            return RuleResult(
                rule_name=self._name,
                passed=False,
                score=0.0,
                reasons=reasons,
                children=guard_results,
                citations=citations,
            )

        inner_result = self.inner.evaluate(snapshot)
        all_children = guard_results + (inner_result,)
        all_citations = tuple({c for r in all_children for c in r.citations})
        return RuleResult(
            rule_name=self._name,
            passed=inner_result.passed,
            score=inner_result.score,
            reasons=inner_result.reasons,
            children=all_children,
            citations=all_citations,
        )
