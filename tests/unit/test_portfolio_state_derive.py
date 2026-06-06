"""
tests/unit/test_portfolio_state_derive.py — Stage portfolio_state_derive 단위 검증.

Covered:
    - empty positions dir → skip_reason
    - single summary → peak == current → drawdown 0
    - multi summaries with peak above current → positive drawdown
    - cash% derivation
    - corrupt summary file → graceful warnings
    - sizing.py integration via load_derived helper
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from domains.risk_engine import portfolio_state_derive as psd


def _write_summary(positions_dir: Path, date: str, payload: dict) -> Path:
    """positions_sync 가 쓰는 envelope 형식으로 _summary-{date}.json 작성."""
    p = positions_dir / f"_summary-{date}.json"
    envelope = {
        "schema": "investment-positions-sync-v1",
        "date": date,
        "payload": payload,
    }
    p.write_text(json.dumps(envelope, ensure_ascii=False), encoding="utf-8")
    return p


def test_empty_positions_dir_skips(isolated_workspace):
    state = psd.derive_state(
        positions_dir=isolated_workspace["positions_dir"],
        date="2026-05-11",
        lookback_days=30,
    )
    assert state.skip_reason is not None
    assert state.summaries_scanned == 0
    assert state.current_drawdown_pct is None
    assert state.current_cash_pct is None


def test_single_summary_drawdown_zero(isolated_workspace):
    pdir = isolated_workspace["positions_dir"]
    _write_summary(
        pdir,
        "2026-05-11",
        {"total_assets_krw": 100_000_000, "cash_krw": 30_000_000},
    )
    state = psd.derive_state(positions_dir=pdir, date="2026-05-11", lookback_days=30)
    assert state.peak_total_assets_krw == 100_000_000
    assert state.current_total_assets_krw == 100_000_000
    assert state.current_drawdown_pct == 0.0
    assert state.current_cash_pct == pytest.approx(0.3)


def test_multi_summary_positive_drawdown(isolated_workspace):
    pdir = isolated_workspace["positions_dir"]
    # peak 2026-04-15 = 120M, current 2026-05-11 = 90M → drawdown = 0.25
    _write_summary(
        pdir, "2026-04-15", {"total_assets_krw": 120_000_000, "cash_krw": 20_000_000}
    )
    _write_summary(
        pdir, "2026-05-11", {"total_assets_krw": 90_000_000, "cash_krw": 25_000_000}
    )
    state = psd.derive_state(positions_dir=pdir, date="2026-05-11", lookback_days=60)
    assert state.peak_total_assets_krw == 120_000_000
    assert state.peak_observed_at == "2026-04-15"
    assert state.current_total_assets_krw == 90_000_000
    assert state.current_drawdown_pct == pytest.approx(0.25, abs=1e-6)
    assert state.current_cash_pct == pytest.approx(25 / 90, abs=1e-4)


def test_corrupt_summary_graceful(isolated_workspace):
    pdir = isolated_workspace["positions_dir"]
    _write_summary(
        pdir, "2026-05-11", {"total_assets_krw": 100_000_000, "cash_krw": 10_000_000}
    )
    # corrupt yesterday
    bad = pdir / "_summary-2026-05-10.json"
    bad.write_text("{ not json", encoding="utf-8")

    state = psd.derive_state(positions_dir=pdir, date="2026-05-11", lookback_days=5)
    # current 정상, corrupt 파일은 warning 로 skip
    assert state.current_total_assets_krw == 100_000_000
    assert any("parse fail" in w for w in state.warnings)


def test_load_derived_returns_payload(isolated_workspace, tmp_path):
    pdir = isolated_workspace["positions_dir"]
    derived_payload = {
        "schema": "investment-portfolio-derived-v1",
        "date": "2026-05-11",
        "current_drawdown_pct": 0.08,
        "current_cash_pct": 0.42,
    }
    envelope = {
        "schema": "investment-portfolio-derived-v1",
        "payload": derived_payload,
    }
    (pdir / "_derived-2026-05-11.json").write_text(
        json.dumps(envelope), encoding="utf-8"
    )
    out = psd.load_derived(pdir, "2026-05-11")
    assert out is not None
    assert out["current_drawdown_pct"] == 0.08
    assert out["current_cash_pct"] == 0.42


def test_load_derived_missing_returns_none(isolated_workspace):
    out = psd.load_derived(isolated_workspace["positions_dir"], "2026-05-11")
    assert out is None
