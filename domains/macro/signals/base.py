"""Signal ABC — macro Stage 0 의 vote-in-signal 플러그인 인터페이스.

각 indicator 가 자기 ``fetch`` (FRED / breadth 수집) + 자기 ``vote`` (임계값 →
regime label) 를 한 클래스에 캡슐화한다. 새 indicator 추가 = ``signals/{name}.py``
에 ``@register_signal`` 클래스 1개 + ``config/regimes.yaml`` 의 ``signals:`` 한 줄
+ ``factory.py`` import 한 줄 — ``main`` / ``classify_regime`` 수술 불요.

설계 경계 (over-abstraction 방지):
- voting aggregation (max-severity) 은 ``application/regime_classify.py`` 의 단일
  함수가 소유. ``VotingStrategy`` ABC 는 도입하지 않는다 (rule-of-three 미충족,
  max-severity 는 1번 사상 doctrine — 단일 함수 seam 으로 충분).
- ``vote`` 는 numeric 결정만. LLM narrative 는 별도 옵셔널 skill (ports 化 X).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Mapping

from domains.macro.domain.regime import IndicatorResult


def empty_indicator(reason: str) -> IndicatorResult:
    """skip / 미수집 indicator 의 표준 표현."""
    return IndicatorResult(
        indicator="",
        value=None,
        value_label="unknown",
        source_citation=None,
        skip_reason=reason,
    )


class Signal(ABC):
    """macro indicator 플러그인. fetch + vote 캡슐화.

    Subclass 는 ``@register_signal("name")`` 로 등록 — ``name`` 이 곧 registry key
    · ``cfg['thresholds']`` 하위키 · indicators dict 키 (3 일치 강제).
    """

    name: str = ""

    @abstractmethod
    def fetch(self, env: Mapping[str, str], date: str) -> tuple[IndicatorResult, list[str]]:
        """indicator 측정값 수집. ``(IndicatorResult, warnings)``."""

    @abstractmethod
    def vote(
        self, result: IndicatorResult, thresholds: Mapping[str, Any]
    ) -> tuple[str, str] | None:
        """``result`` → ``(regime_vote, rationale)`` 또는 None (vote 없음 / skip).

        ``thresholds`` 는 ``cfg['thresholds']`` 전체 — signal 이 자기 하위키
        (= ``self.name``) 를 선택해 읽는다.
        """
