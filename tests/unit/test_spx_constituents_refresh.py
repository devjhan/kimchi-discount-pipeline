"""tests/unit/test_spx_constituents_refresh.py — SPX cache refresh staleness gate (D-2)."""

from __future__ import annotations

from pathlib import Path

import pytest

from domains.macro import spx_constituents_refresh as spx

pytestmark = pytest.mark.unit


def test_cache_age_days_none_when_no_observed() -> None:
    assert spx._cache_age_days({}) is None
    assert spx._cache_age_days({"payload": {}}) is None


def test_cache_age_days_computes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(spx, "now_iso_kst", lambda: "2026-06-10T09:00:00+09:00")
    age = spx._cache_age_days({"payload": {"observed_at": "2026-06-01T09:00:00+09:00"}})
    assert age == 9


def test_main_skips_when_fresh(monkeypatch: pytest.MonkeyPatch) -> None:
    """fresh cache (age < max_age_days) → fetch self-skip (no network)."""
    monkeypatch.setattr(spx, "now_iso_kst", lambda: "2026-06-10T09:00:00+09:00")
    monkeypatch.setattr(
        spx, "load_cached", lambda: {"payload": {"observed_at": "2026-06-05T09:00:00+09:00"}}
    )

    def _boom() -> list[str]:
        raise AssertionError("fetch_constituents must not run when cache is fresh")

    monkeypatch.setattr(spx, "fetch_constituents", _boom)
    monkeypatch.setattr(spx, "emit_summary", lambda *a, **k: None)
    assert spx.main(["--max-age-days", "30"]) == 0


def test_main_fetches_when_stale(monkeypatch: pytest.MonkeyPatch) -> None:
    """미존재/stale cache → fetch 진행 (gate 통과)."""
    monkeypatch.setattr(spx, "now_iso_kst", lambda: "2026-06-10T09:00:00+09:00")
    monkeypatch.setattr(spx, "load_cached", lambda: {})  # 캐시 없음 → age None → stale
    called = {"n": 0}

    def _fetch() -> list[str]:
        called["n"] += 1
        return ["AAPL", "MSFT"]

    written: dict[str, object] = {}

    def _write(path: Path, envelope: object) -> Path:
        written["envelope"] = envelope
        return path

    monkeypatch.setattr(spx, "fetch_constituents", _fetch)
    monkeypatch.setattr(spx, "write_output_safely", _write)
    monkeypatch.setattr(spx, "emit_summary", lambda *a, **k: None)
    assert spx.main(["--max-age-days", "30"]) == 0
    assert called["n"] == 1
    assert written["envelope"]["payload"]["tickers"] == ["AAPL", "MSFT"]  # type: ignore[index]
