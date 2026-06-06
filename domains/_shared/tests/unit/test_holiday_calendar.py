"""domains/_shared/tests/unit/test_holiday_calendar.py — KRX holiday calendar."""

from __future__ import annotations

import pytest

from infrastructure._common import utils
from infrastructure._common.utils import (
    is_trading_day,
    load_holidays,
    normalize_to_trading_day,
)

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def reset_cache() -> None:
    """각 테스트 전에 module-level cache 초기화 (test isolation)."""
    utils._HOLIDAYS_CACHE.clear()
    utils._HOLIDAYS_META_CACHE.clear()
    yield
    utils._HOLIDAYS_CACHE.clear()
    utils._HOLIDAYS_META_CACHE.clear()


class TestLoadHolidays:
    def test_krx_loads(self) -> None:
        out = load_holidays("KRX")
        # 최소한 _holidays_krx.json 의 알려진 휴일 포함
        assert "2026-01-01" in out  # 신정
        assert "2026-05-05" in out  # 어린이날
        assert "2026-08-17" in out  # 광복절 대체
        assert "2026-12-25" in out  # 크리스마스

    def test_unknown_market_returns_empty(self) -> None:
        assert load_holidays("UNKNOWN") == set()

    def test_cache_hit(self) -> None:
        a = load_holidays("KRX")
        b = load_holidays("KRX")
        assert a is b  # same set object — cached


class TestIsTradingDay:
    def test_weekday_no_holiday(self) -> None:
        # 2026-05-08 (금)
        assert is_trading_day("2026-05-08") is True

    def test_saturday(self) -> None:
        assert is_trading_day("2026-05-09") is False

    def test_sunday(self) -> None:
        assert is_trading_day("2026-05-10") is False

    def test_new_year(self) -> None:
        assert is_trading_day("2026-01-01") is False

    def test_childrens_day(self) -> None:
        assert is_trading_day("2026-05-05") is False

    def test_christmas(self) -> None:
        assert is_trading_day("2026-12-25") is False


class TestNormalizeToTradingDay:
    def test_weekday_passthrough(self) -> None:
        assert normalize_to_trading_day("2026-05-08") == "2026-05-08"

    def test_saturday_skips_to_friday(self) -> None:
        assert normalize_to_trading_day("2026-05-09") == "2026-05-08"

    def test_sunday_skips_to_friday(self) -> None:
        assert normalize_to_trading_day("2026-05-10") == "2026-05-08"

    def test_new_year_skips_back(self) -> None:
        # 2026-01-01 (목) 신정 → 2025-12-31 도 신정/대체 → 휴일 → 2025-12-30 (화)
        # _holidays_krx.json 에 2025-12-31 포함되어 있으므로
        out = normalize_to_trading_day("2026-01-01")
        assert out == "2025-12-30"

    def test_childrens_day_skips_to_previous_friday(self) -> None:
        # 2026-05-05 (화) 휴일 → 2026-05-04 (월)
        assert normalize_to_trading_day("2026-05-05") == "2026-05-04"

    def test_consecutive_holidays(self) -> None:
        # 추석 연휴 시뮬: 2026-09-24~25 (목금) 연휴 → 그 전 영업일은 9-23 (수)
        # 2026-09-25 입력 → 9-24 도 휴일 → 9-23 (수)
        assert normalize_to_trading_day("2026-09-25") == "2026-09-23"
