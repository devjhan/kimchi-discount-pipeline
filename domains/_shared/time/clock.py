"""AsOfClock — 시점 t 의 1급 시민. 모든 IO 함수의 필수 인자.

원래 ``domains/screener/time/clock.py`` 에 정의되어 있던 클래스를
2026-05-17 에 본 모듈로 이전. screener / universe / macro 등 모든 도메인이
*동일 객체 클래스* 를 import 해 비교 / 정렬 / 해시 일관성을 가진다.

라이브 cron 은 ``AsOfClock.now()`` default 로 무의식, 백테스트 도입 시
``AsOfClock.at_market_close(date)`` 또는 ``at_eod(date)`` 로 1줄 override.

invariants:
- tz-aware datetime 만 허용 (naive 입력은 ValueError)
- 내부적으로 KST 로 정규화
- frozen + order — 비교 / 해시 / 정렬 가능
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time

from infrastructure._common.utils import KST


def now_kst() -> datetime:
    """현재 KST datetime (tz-aware)."""
    return datetime.now(KST)


@dataclass(frozen=True, order=True)
class AsOfClock:
    """시점 t 를 단일 객체로 표현."""

    as_of: datetime

    def __post_init__(self) -> None:
        if self.as_of.tzinfo is None:
            raise ValueError(
                "AsOfClock requires tz-aware datetime. "
                "AsOfClock.at_market_close(date(...)) 또는 tz-aware datetime 전달."
            )
        if self.as_of.tzinfo is not KST:
            object.__setattr__(self, "as_of", self.as_of.astimezone(KST))

    @classmethod
    def now(cls) -> "AsOfClock":
        """현재 KST 시각으로 clock 생성."""
        return cls(now_kst())

    @classmethod
    def at_market_close(cls, d: date) -> "AsOfClock":
        """정규장 마감 (15:30 KST). 일일 스크리닝 default."""
        return cls(datetime.combine(d, time(15, 30, 0), tzinfo=KST))

    @classmethod
    def at_market_open(cls, d: date) -> "AsOfClock":
        """정규장 시가 (09:00 KST). 백테스트 리밸런싱 default."""
        return cls(datetime.combine(d, time(9, 0, 0), tzinfo=KST))

    @classmethod
    def at_eod(cls, d: date) -> "AsOfClock":
        """End-of-day (23:59:59 KST). date-only DART 공시 가시화 기준."""
        return cls(datetime.combine(d, time(23, 59, 59), tzinfo=KST))

    def can_see(self, event_time: datetime) -> bool:
        """event_time 이 clock 이전(또는 동일)이면 가시 — IO layer 에서만 호출."""
        if event_time.tzinfo is None:
            raise ValueError("event_time 은 tz-aware 이어야 함")
        return event_time.astimezone(KST) <= self.as_of

    @property
    def trading_date(self) -> date:
        """clock 의 거래일 (KST 날짜)."""
        return self.as_of.date()

    def __str__(self) -> str:
        return self.as_of.isoformat(timespec="seconds")
