"""CatalystDetector ABC — 모든 catalyst detector 의 공통 인터페이스.

universe ``sources/base.py`` (DiscoverySource) 와 동등한 layer — 각 detector 가
독립적으로 catalyst event 를 emit 하고 ``application/scan_catalysts.py`` 가 fan-in
한다. cross-detector 집계 (G15 d_type augment) 는 detector 가 아니라 orchestrator
책임.

구현 규약:
1. ``@dataclass(frozen=True)`` — instantiated 후 상태 불변
2. ``@register_detector("type_name")`` decorator 로 registry 등록
3. ``name: str`` / ``enabled: bool`` 필드
4. ``from_spec(spec)`` classmethod — ``config/detectors.yaml`` 의 단일 spec → instance
5. ``detect(ctx)`` — 본 detector 가 발견한 events + warnings 산출
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Mapping

from domains.catalyst.domain.event import CatalystEvent


@dataclass(frozen=True)
class DetectContext:
    """Detector.detect() 에 주입되는 외부 환경.

    - ``env`` — ``.env`` 의 모든 키 (secret 포함, 본문 노출 금지)
    - ``universe`` — {ticker: name} (G14 membership + name lookup)
    - ``universe_market`` — {stock_code: market} (earnings/yahoo 가격 fetch 용)
    - ``date`` — 거래일 ISO (YYYY-MM-DD)
    - ``fetched_at`` — detection 시각 ISO_KST (event.detected_at)
    - ``allow_yahoo`` — KIS 미가용 시 Yahoo fallback 허용 여부
    """

    env: Mapping[str, str]
    universe: Mapping[str, str]
    universe_market: Mapping[str, str]
    date: str
    fetched_at: str
    allow_yahoo: bool = False


@dataclass(frozen=True)
class DetectResult:
    """단일 detector 의 detect() 산출.

    - ``events`` — 발견된 CatalystEvent tuple (빈 tuple 도 정상)
    - ``warnings`` — human-readable 진단 메시지 (G8 graceful degradation 추적)
    """

    events: tuple[CatalystEvent, ...]
    warnings: tuple[str, ...]


class CatalystDetector(ABC):
    """모든 catalyst detector 의 공통 인터페이스."""

    name: str
    enabled: bool

    @classmethod
    @abstractmethod
    def from_spec(cls, spec: dict[str, Any]) -> "CatalystDetector":
        """``config/detectors.yaml`` 의 단일 detector spec 을 인스턴스로 변환."""

    @abstractmethod
    def detect(self, ctx: DetectContext) -> DetectResult:
        """본 detector 가 발견한 events + warnings 산출."""
