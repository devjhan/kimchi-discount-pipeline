"""Enricher ABC — source_category 별 attribute attachment 의 공통 인터페이스.

DiscoverySource 와 동등 layer. 차이:
- DiscoverySource 는 외부에서 entries 를 *발견* (fan-in collector)
- Enricher 는 발견된 entries 에 *attribute attach* (vector mapper, partial application)

설계 원칙:
- frozen dataclass — 인스턴스는 상태 불변
- ``applies_to: frozenset[str]`` — 본 enricher 가 attach 할 source_category 집합
  (cross-attach 방지 — 의도된 책임 분리)
- ``from_spec(yaml_dict)`` classmethod — YAML spec → 인스턴스 (factory 가 호출)
- ``enrich(entry, ctx)`` — 단일 entry 의 EnrichmentResult 반환
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Mapping

from domains._shared.time.clock import AsOfClock
from domains.universe.domain.enriched import EnrichmentResult
from domains.universe.domain.entry import UniverseEntry


@dataclass(frozen=True)
class EnrichContext:
    """Enricher.enrich() 에 주입되는 외부 환경.

    - ``clock`` — 가시화 기준 시점 (백테스트 lookahead bias 차단)
    - ``env`` — ``.env`` 의 모든 키 (secret 포함, 본문 노출 금지)
    - ``allow_yahoo`` — KIS 미가용 시 Yahoo 사용 여부 (CLI 또는 behavior.yaml)
    """

    clock: AsOfClock
    env: Mapping[str, str]
    allow_yahoo: bool = False


class Enricher(ABC):
    """모든 universe enricher 의 공통 인터페이스.

    구현 클래스 규약:
    1. ``@dataclass(frozen=True)`` — instantiated 후 상태 불변
    2. ``@register_enricher("type_name")`` decorator 로 registry 등록
    3. ``name: str`` 필드 — config 의 ``name:`` (인스턴스 식별자)
    4. ``applies_to: frozenset[str]`` 필드 — 매칭 source_category 집합
    5. ``from_spec(spec)`` classmethod — YAML dict → instance
    6. ``enrich(entry, ctx)`` 메서드 — EnrichmentResult 반환
    """

    name: str
    applies_to: frozenset[str]

    @classmethod
    @abstractmethod
    def from_spec(cls, spec: dict[str, Any]) -> "Enricher":
        """``config/enrichers.yaml`` 의 단일 enricher spec 을 인스턴스로 변환."""

    @abstractmethod
    def enrich(self, entry: UniverseEntry, ctx: EnrichContext) -> EnrichmentResult:
        """단일 entry 에 attribute attach. caller 가 ``applies_to`` filter 후 호출."""
