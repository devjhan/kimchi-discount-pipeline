"""ClockPort — AsOfClock 의 형식 port (순수 typing, 무-wiring).

``domains/_shared/time/clock.py`` 의 ``AsOfClock`` 가 *구조적으로* 만족하는 read 계약.
IO layer 가 가시성(``can_see``) · 거래일(``trading_date``) 판단에 의존할 때 본 Protocol
로 타입을 좁혀 구체 clock 구현에서 분리한다. ``clock.py`` 자체는 변경하지 않는다 —
본 모듈은 이미 전역 주입되는 clock 을 *명명된 port* 로 형식화할 뿐이다 (Phase 0).
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Protocol, runtime_checkable


@runtime_checkable
class ClockPort(Protocol):
    """시점 t read 계약 — AsOfClock 구조 매치 (frozen value)."""

    @property
    def as_of(self) -> datetime:
        """clock 의 시점 (tz-aware KST datetime)."""
        ...

    @property
    def trading_date(self) -> date:
        """clock 의 거래일 (KST 날짜)."""
        ...

    def can_see(self, event_time: datetime) -> bool:
        """event_time 이 시점 t 이전(또는 동일)이면 가시 — IO layer 한정."""
        ...
