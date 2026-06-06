"""Rule ABC — 모든 Rule 의 평가 인터페이스.

3 핵심 anchor 중 1: Rule.evaluate 시그너처는 clock 받지 않는다. 시점 가시화는
IO layer (PointInTimeFinancialCache) 의 책임이며 snapshot 자체가 이미 시점
정합. clock 을 받기 시작하면 백테스트 결정론 single point of control 가 깨짐.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from domains.screener.domain.ticker import TickerSnapshot
from domains.screener.domain.verdict import RuleResult


class Rule(ABC):
    """모든 Rule 의 base. leaf / composite 모두 본 인터페이스 준수."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Rule 의 식별자 (factory 가 YAML 의 name 필드에서 주입)."""

    @abstractmethod
    def evaluate(self, snapshot: TickerSnapshot) -> RuleResult:
        """단일 ticker snapshot 에 대해 평가. RuleResult 반환."""
