"""DiscoverySource ABC — 모든 universe discovery source 의 공통 인터페이스.

screener 의 ``Rule`` ABC 와 동등한 layer. 단 fan-in collector 패턴이라
Composite tree (And/Or/Not) 가 없음 — 각 source 가 독립적으로 entries 를 emit
하고 ``application/build_universe.py`` (Run 4) 가 union 으로 합산.

설계 원칙:
- frozen dataclass — 한 번 생성된 source 인스턴스는 상태 불변
- ``from_spec(yaml_dict)`` classmethod — YAML 스펙 파싱 단일 지점 (factory 가 호출)
- ``discover(ctx)`` — 본 source 가 발견한 entries + warnings 산출
- ``SourceResult.degraded=True`` — progressive degrade retry 발동 여부 (Run 3
  DartDisclosureFilter 활용)
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Mapping

from domains._shared.time.clock import AsOfClock
from domains.universe.domain.entry import UniverseEntry


@dataclass(frozen=True)
class DiscoveryContext:
    """Source.discover() 에 주입되는 외부 환경.

    - ``clock`` — 발견 시점 (백테스트는 과거 시점, 라이브는 ``AsOfClock.now()``)
    - ``env`` — ``.env`` 의 모든 키 (secret 포함, 본문 노출 금지)
    """

    clock: AsOfClock
    env: Mapping[str, str]


@dataclass(frozen=True)
class SourceResult:
    """단일 source 의 discover() 산출.

    - ``entries`` — 발견된 UniverseEntry tuple (빈 tuple 도 정상)
    - ``warnings`` — human-readable 진단 메시지 (G8 graceful degradation 추적)
    - ``degraded`` — progressive degrade retry 가 발동했는지 (Run 3 활용 — Run 2
      source 들은 모두 False)
    """

    entries: tuple[UniverseEntry, ...]
    warnings: tuple[str, ...]
    degraded: bool = False


class DiscoverySource(ABC):
    """모든 universe discovery source 의 공통 인터페이스.

    구현 클래스 규약:
    1. ``@dataclass(frozen=True)`` 로 정의 — instantiated 후 상태 불변
    2. ``@register_source("type_name")`` decorator 로 registry 등록
    3. ``name: str`` 필드 — config 의 ``name:`` (인스턴스 식별자)
    4. ``source_category: str`` 필드 — emit 하는 UniverseEntry 의 source_category
    5. ``from_spec(spec)`` classmethod — YAML dict → instance
    6. ``discover(ctx)`` 메서드 — entries + warnings 산출
    """

    name: str
    source_category: str

    @classmethod
    @abstractmethod
    def from_spec(cls, spec: dict[str, Any]) -> "DiscoverySource":
        """``config/sources.yaml`` 의 단일 source spec 을 인스턴스로 변환."""

    @abstractmethod
    def discover(self, ctx: DiscoveryContext) -> SourceResult:
        """본 source 가 발견한 entries + warnings 산출. side-effect 최소화."""
