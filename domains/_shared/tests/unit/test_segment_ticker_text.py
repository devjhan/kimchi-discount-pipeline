"""segment_registry — ticker 텍스트 source 단위 테스트 (Task 8)."""
from __future__ import annotations

import pytest

from domains._shared.adapters.ticker_text import (
    CompositeTickerTextSource,
    DartTickerTextSource,
    ManualTickerTextSource,
)
from domains._shared.ports.ticker_text import TickerTextSource


@pytest.mark.unit
def test_manual_is_port() -> None:
    assert isinstance(ManualTickerTextSource(), TickerTextSource)


@pytest.mark.unit
def test_manual_lookup() -> None:
    src = ManualTickerTextSource({"KR:003550": "지주사 사업 내용"})
    assert src.text_for("KR:003550") == "지주사 사업 내용"
    assert src.text_for("KR:999999") == ""


@pytest.mark.unit
def test_composite_priority_fallback() -> None:
    primary = ManualTickerTextSource({"KR:A": "manual A"})
    secondary = ManualTickerTextSource({"KR:A": "dart A", "KR:B": "dart B"})
    comp = CompositeTickerTextSource([primary, secondary])
    assert comp.text_for("KR:A") == "manual A"  # 수기 우선
    assert comp.text_for("KR:B") == "dart B"  # fallback
    assert comp.text_for("KR:C") == ""


@pytest.mark.unit
def test_dart_source_is_port() -> None:
    assert isinstance(
        DartTickerTextSource(fetch=lambda c: "", corp_index={}), TickerTextSource
    )


@pytest.mark.unit
def test_dart_source_maps_ticker_to_corp_and_truncates() -> None:
    calls: list[str] = []

    def _fetch(corp_code: str) -> str:
        calls.append(corp_code)
        return "사업의 내용 " * 100

    src = DartTickerTextSource(
        fetch=_fetch, corp_index={"003550": "00126380"}, max_chars=20
    )
    text = src.text_for("KR:003550")
    assert calls == ["00126380"]  # 6자리 stock_code → 8자리 corp_code 매핑
    assert len(text) == 20  # max_chars 절단


@pytest.mark.unit
def test_dart_source_unknown_ticker_returns_empty() -> None:
    src = DartTickerTextSource(fetch=lambda c: "x", corp_index={})
    assert src.text_for("KR:999999") == ""  # corp_index miss → fetch 호출 안 함


@pytest.mark.unit
def test_dart_source_fetch_failure_is_graceful() -> None:
    def _boom(corp_code: str) -> str:
        raise RuntimeError("DART 503")

    src = DartTickerTextSource(fetch=_boom, corp_index={"003550": "00126380"})
    assert src.text_for("KR:003550") == ""  # 절대 raise 안 함 (G8)
