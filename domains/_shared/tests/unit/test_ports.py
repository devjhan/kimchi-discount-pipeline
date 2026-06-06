"""domains/_shared/ports Protocol 계약 테스트.

ClockPort ↔ AsOfClock 구조 매치, CitationPort runtime_checkable 동작 검증.
Protocol 이 dead 가 아님을 보장 + 구조 drift 방지.
"""
from __future__ import annotations

from datetime import date

import pytest

from domains._shared.ports.citation import CitationPort
from domains._shared.ports.clock import ClockPort
from domains._shared.time.clock import AsOfClock


@pytest.mark.unit
def test_asofclock_satisfies_clockport() -> None:
    """AsOfClock 인스턴스가 ClockPort 를 구조적으로 만족 (runtime_checkable)."""
    clock = AsOfClock.at_market_close(date(2026, 5, 15))
    assert isinstance(clock, ClockPort)
    assert clock.trading_date == date(2026, 5, 15)


class _Cite:
    """CitationPort 최소 구현 (테스트용)."""

    def format(self, source: str, ts: str, value: object) -> str:
        """G7 형식 문자열."""
        return f"{source}@{ts}={value}"


@pytest.mark.unit
def test_citation_impl_satisfies_port() -> None:
    """format 메서드 객체가 CitationPort 를 만족 + 호출 동작."""
    cite: CitationPort = _Cite()
    assert isinstance(cite, CitationPort)
    assert cite.format("DART", "2026-05-15T15:30:00+09:00", {"k": 1}) == (
        "DART@2026-05-15T15:30:00+09:00={'k': 1}"
    )


@pytest.mark.unit
def test_non_citation_object_fails_isinstance() -> None:
    """format 없는 객체는 CitationPort 미충족 (runtime_checkable 음성 케이스)."""
    assert not isinstance(object(), CitationPort)
