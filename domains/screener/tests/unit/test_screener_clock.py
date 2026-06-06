"""AsOfClock 단위 테스트 — tz-aware 강제, can_see, factory methods."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from domains._shared.time.clock import AsOfClock

KST = timezone(timedelta(hours=9))


@pytest.mark.unit
def test_naive_datetime_rejected() -> None:
    """naive datetime 입력은 ValueError."""
    with pytest.raises(ValueError):
        AsOfClock(datetime(2026, 5, 15, 15, 30))


@pytest.mark.unit
def test_factory_at_market_close() -> None:
    clock = AsOfClock.at_market_close(date(2026, 5, 15))
    assert clock.trading_date == date(2026, 5, 15)
    assert clock.as_of.hour == 15 and clock.as_of.minute == 30
    assert clock.as_of.tzinfo == KST


@pytest.mark.unit
def test_factory_at_eod() -> None:
    clock = AsOfClock.at_eod(date(2026, 5, 15))
    assert clock.as_of.hour == 23 and clock.as_of.minute == 59
    assert clock.as_of.second == 59


@pytest.mark.unit
def test_can_see_visible_event() -> None:
    clock = AsOfClock.at_market_close(date(2026, 5, 15))
    earlier = datetime(2026, 5, 15, 9, 0, tzinfo=KST)
    assert clock.can_see(earlier)


@pytest.mark.unit
def test_can_see_future_event_invisible() -> None:
    clock = AsOfClock.at_market_close(date(2026, 5, 15))
    later = datetime(2026, 5, 16, 9, 0, tzinfo=KST)
    assert not clock.can_see(later)


@pytest.mark.unit
def test_can_see_naive_event_rejected() -> None:
    clock = AsOfClock.at_market_close(date(2026, 5, 15))
    with pytest.raises(ValueError):
        clock.can_see(datetime(2026, 5, 15, 9, 0))


@pytest.mark.unit
def test_clock_ordering() -> None:
    earlier = AsOfClock.at_market_close(date(2026, 5, 14))
    later = AsOfClock.at_market_close(date(2026, 5, 15))
    assert earlier < later
