"""tests/integration/test_event_falsifier_linker_e2e.py — Event Falsifier Linker E2E."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from domains.risk_engine.event_falsifier_linker import main

# F-8: main() 의 path 주입 seam (_positions_dir / _trail_dir) 은 application layer 로 이전.
_APP_MOD = "domains.risk_engine.application.event_falsifier_linker"

pytestmark = pytest.mark.integration

TODAY = "2026-05-08"  # 2026-05-09는 토요일 → normalize_to_trading_day가 05-08(금)으로 변환


def _write_thesis(positions_dir: Path, ticker_safe: str, data: dict) -> None:
    d = positions_dir / ticker_safe
    d.mkdir(parents=True, exist_ok=True)
    (d / "thesis.json").write_text(json.dumps(data), encoding="utf-8")


def _make_position(ticker: str, spec: dict, status: str = "open") -> dict:
    return {
        "ticker": ticker,
        "name": ticker,
        "status": status,
        "entry_date": "2026-01-15",
        "entry_price_krw": 80000,
        "thesis": {
            "entry_catalyst": "test",
            "falsifier": {"category": "event_trigger", "spec": spec},
            "time_horizon_months": 18,
            "edge_source": ["C"],
        },
    }


def _write_stage3(trail_dir: Path, catalysts: list, orphans: list | None = None) -> None:
    payload = {
        "schema": "investment-stage3-catalyst-events-v1",
        "catalysts": catalysts,
        "d_type_orphans": orphans or [],
        "warnings": [],
    }
    (trail_dir / "03-catalyst-events.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )


# ============================================================
# Tests
# ============================================================

def test_cli_dry_run_empty_positions(tmp_path: Path):
    positions_dir = tmp_path / "_positions"
    positions_dir.mkdir()
    trail_dir = tmp_path / "trail"
    trail_dir.mkdir()

    rc = main([
        "--dry-run",
        "--date", TODAY,
        "--trail-dir", str(trail_dir),
    ])
    assert rc == 0
    out = trail_dir / f"event-trigger-status-{TODAY}.json"
    assert out.exists()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["stats"]["total_event_trigger_positions"] == 0
    assert "--dry-run" in str(data["warnings"])


def test_cli_no_stage3_file_graceful(tmp_path: Path, monkeypatch):
    positions_dir = tmp_path / "_positions"
    trail_dir = tmp_path / "trail"
    trail_dir.mkdir()

    _write_thesis(positions_dir, "KR_003550", _make_position(
        "KR:003550",
        {"watch_catalyst_type": "activist_5pct_filing", "direction": "absence"},
    ))

    monkeypatch.setattr(
        f"{_APP_MOD}._positions_dir",
        lambda: positions_dir,
    )
    monkeypatch.setattr(
        f"{_APP_MOD}._trail_dir",
        lambda *a, **k: trail_dir,
    )

    rc = main(["--date", TODAY, "--trail-dir", str(trail_dir)])
    assert rc == 0
    out = trail_dir / f"event-trigger-status-{TODAY}.json"
    data = json.loads(out.read_text(encoding="utf-8"))
    # Stage 3 missing → warning, position exists but signal unspecified or triggered
    assert len(data["warnings"]) >= 1
    assert data["stats"]["total_event_trigger_positions"] == 1
    # Stage 3 not found → seen_today=False → direction=absence → triggered
    assert data["records"][0]["signal"] == "triggered"


def test_cli_full_flow_presence_triggered(tmp_path: Path, monkeypatch):
    positions_dir = tmp_path / "_positions"
    trail_dir = tmp_path / "trail"
    trail_dir.mkdir()

    _write_thesis(positions_dir, "KR_003550", _make_position(
        "KR:003550",
        {"watch_catalyst_type": "treasury_share_cancellation", "direction": "presence"},
    ))
    _write_stage3(trail_dir, catalysts=[{
        "ticker": "KR:003550",
        "catalyst_type": "treasury_share_cancellation",
        "trigger_class": "a_type",
        "detected_at": f"{TODAY}T09:00:00+09:00",
        "source_citation": f"DART@{TODAY}=test",
    }])

    monkeypatch.setattr(
        f"{_APP_MOD}._positions_dir",
        lambda: positions_dir,
    )
    monkeypatch.setattr(
        f"{_APP_MOD}._trail_dir",
        lambda *a, **k: trail_dir,
    )

    rc = main(["--date", TODAY, "--trail-dir", str(trail_dir)])
    assert rc == 0
    out = trail_dir / f"event-trigger-status-{TODAY}.json"
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["stats"]["triggered"] == 1
    assert data["records"][0]["signal"] == "triggered"
    assert data["records"][0]["needs_user_decision"] is True
    assert f"DART@{TODAY}=test" in data["records"][0]["source_citations"]


def test_cli_full_flow_presence_not_triggered(tmp_path: Path, monkeypatch):
    positions_dir = tmp_path / "_positions"
    trail_dir = tmp_path / "trail"
    trail_dir.mkdir()

    _write_thesis(positions_dir, "KR_003550", _make_position(
        "KR:003550",
        {"watch_catalyst_type": "activist_5pct_filing", "direction": "presence"},
    ))
    # Stage 3 has no catalyst for this ticker
    _write_stage3(trail_dir, catalysts=[])

    monkeypatch.setattr(
        f"{_APP_MOD}._positions_dir",
        lambda: positions_dir,
    )
    monkeypatch.setattr(
        f"{_APP_MOD}._trail_dir",
        lambda *a, **k: trail_dir,
    )

    rc = main(["--date", TODAY, "--trail-dir", str(trail_dir)])
    assert rc == 0
    out = trail_dir / f"event-trigger-status-{TODAY}.json"
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["records"][0]["signal"] == "not_triggered"
    assert data["records"][0]["needs_user_decision"] is False


def test_cli_no_spec_watch_catalyst_unspecified(tmp_path: Path, monkeypatch):
    positions_dir = tmp_path / "_positions"
    trail_dir = tmp_path / "trail"
    trail_dir.mkdir()

    _write_thesis(positions_dir, "KR_003550", _make_position(
        "KR:003550",
        {},  # no watch_catalyst_type
    ))
    _write_stage3(trail_dir, catalysts=[])

    monkeypatch.setattr(
        f"{_APP_MOD}._positions_dir",
        lambda: positions_dir,
    )
    monkeypatch.setattr(
        f"{_APP_MOD}._trail_dir",
        lambda *a, **k: trail_dir,
    )

    rc = main(["--date", TODAY, "--trail-dir", str(trail_dir)])
    assert rc == 0
    out = trail_dir / f"event-trigger-status-{TODAY}.json"
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["records"][0]["signal"] == "unspecified"
    assert data["records"][0]["needs_user_decision"] is True
    assert data["stats"]["unspecified"] == 1
