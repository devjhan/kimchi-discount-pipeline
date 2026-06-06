"""tests/unit/test_event_falsifier_linker.py — Event Falsifier Linker (pure functions)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from domains.risk_engine.event_falsifier_linker import (
    EventTriggerStatus,
    _build_stage3_index,
    evaluate_position,
    load_event_trigger_positions,
    load_stage3_catalysts,
)

pytestmark = pytest.mark.unit

TODAY = "2026-05-09"

# ============================================================
# Fixtures / helpers
# ============================================================

def _make_position(
    ticker: str = "KR:003550",
    name: str = "LG",
    status: str = "open",
    falsifier_category: str = "event_trigger",
    spec: dict | None = None,
) -> dict:
    return {
        "ticker": ticker,
        "name": name,
        "status": status,
        "entry_date": "2026-01-15",
        "entry_price_krw": 84000,
        "thesis": {
            "entry_catalyst": "activist 5% 신고",
            "falsifier": {
                "category": falsifier_category,
                "spec": spec or {},
            },
            "time_horizon_months": 18,
            "edge_source": ["C", "D"],
        },
    }


def _make_catalyst(
    ticker: str = "KR:003550",
    catalyst_type: str = "activist_5pct_filing",
    source_citation: str = "DART@2026-05-09=test",
) -> dict:
    return {
        "ticker": ticker,
        "catalyst_type": catalyst_type,
        "trigger_class": "d_type",
        "detected_at": "2026-05-09T09:00:00+09:00",
        "source_citation": source_citation,
    }


# ============================================================
# evaluate_position — signal logic
# ============================================================

def test_no_watch_catalyst_type_is_unspecified():
    pos = _make_position(spec={})
    idx = _build_stage3_index([_make_catalyst()])
    rec = evaluate_position(pos, idx, TODAY)
    assert rec.signal == "unspecified"
    assert rec.seen_today is None
    assert rec.needs_user_decision is True


def test_presence_seen_triggered():
    pos = _make_position(spec={
        "watch_catalyst_type": "activist_5pct_filing",
        "direction": "presence",
    })
    idx = _build_stage3_index([_make_catalyst(catalyst_type="activist_5pct_filing")])
    rec = evaluate_position(pos, idx, TODAY)
    assert rec.signal == "triggered"
    assert rec.seen_today is True
    assert rec.needs_user_decision is True


def test_presence_not_seen_not_triggered():
    pos = _make_position(spec={
        "watch_catalyst_type": "activist_5pct_filing",
        "direction": "presence",
    })
    idx = _build_stage3_index([])  # empty — not seen
    rec = evaluate_position(pos, idx, TODAY)
    assert rec.signal == "not_triggered"
    assert rec.seen_today is False
    assert rec.needs_user_decision is False


def test_absence_seen_not_triggered():
    pos = _make_position(spec={
        "watch_catalyst_type": "activist_5pct_filing",
        "direction": "absence",
    })
    idx = _build_stage3_index([_make_catalyst(catalyst_type="activist_5pct_filing")])
    rec = evaluate_position(pos, idx, TODAY)
    assert rec.signal == "not_triggered"
    assert rec.seen_today is True
    assert rec.needs_user_decision is False


def test_absence_not_seen_triggered():
    pos = _make_position(spec={
        "watch_catalyst_type": "activist_5pct_filing",
        "direction": "absence",
    })
    idx = _build_stage3_index([])
    rec = evaluate_position(pos, idx, TODAY)
    assert rec.signal == "triggered"
    assert rec.seen_today is False
    assert rec.needs_user_decision is True


def test_different_catalyst_type_no_match():
    pos = _make_position(spec={
        "watch_catalyst_type": "activist_5pct_filing",
        "direction": "presence",
    })
    # Stage 3 has a different catalyst type for same ticker
    idx = _build_stage3_index([_make_catalyst(catalyst_type="treasury_share_cancellation")])
    rec = evaluate_position(pos, idx, TODAY)
    assert rec.seen_today is False
    assert rec.signal == "not_triggered"
    assert len(rec.stage3_matches) == 0


def test_citations_include_stage3_source():
    citation = "DART@2026-05-09=activist_test"
    pos = _make_position(spec={
        "watch_catalyst_type": "activist_5pct_filing",
        "direction": "presence",
    })
    cat = _make_catalyst(source_citation=citation)
    idx = _build_stage3_index([cat])
    rec = evaluate_position(pos, idx, TODAY)
    assert citation in rec.source_citations


def test_position_citation_always_included():
    pos = _make_position(spec={})
    idx = _build_stage3_index([])
    rec = evaluate_position(pos, idx, TODAY)
    assert any("POSITION" in c for c in rec.source_citations)


def test_unspecified_direction_value():
    pos = _make_position(spec={
        "watch_catalyst_type": "activist_5pct_filing",
        "direction": "unknown_value",
    })
    idx = _build_stage3_index([_make_catalyst()])
    rec = evaluate_position(pos, idx, TODAY)
    assert rec.signal == "unspecified"
    assert rec.needs_user_decision is True


def test_ticker_not_in_stage3_index():
    pos = _make_position(ticker="KR:999999", spec={
        "watch_catalyst_type": "activist_5pct_filing",
        "direction": "presence",
    })
    idx = _build_stage3_index([_make_catalyst(ticker="KR:003550")])
    rec = evaluate_position(pos, idx, TODAY)
    assert rec.seen_today is False
    assert rec.stage3_matches == []


# ============================================================
# load_event_trigger_positions
# ============================================================

def test_only_event_trigger_positions_returned(tmp_path: Path):
    positions_dir = tmp_path / "_positions"
    for i, category in enumerate(["time_cap", "metric_trigger", "event_trigger"]):
        ticker_dir = positions_dir / f"KR_00000{i}"
        ticker_dir.mkdir(parents=True)
        pos = _make_position(ticker=f"KR:00000{i}", falsifier_category=category)
        (ticker_dir / "thesis.json").write_text(
            json.dumps(pos), encoding="utf-8"
        )
    result, warnings = load_event_trigger_positions(positions_dir)
    assert len(result) == 1
    assert result[0]["ticker"] == "KR:000002"
    assert warnings == []


def test_closed_positions_excluded(tmp_path: Path):
    positions_dir = tmp_path / "_positions"
    ticker_dir = positions_dir / "KR_003550"
    ticker_dir.mkdir(parents=True)
    pos = _make_position(status="closed", falsifier_category="event_trigger")
    (ticker_dir / "thesis.json").write_text(json.dumps(pos), encoding="utf-8")
    result, _ = load_event_trigger_positions(positions_dir)
    assert result == []


def test_empty_positions_dir(tmp_path: Path):
    result, warnings = load_event_trigger_positions(tmp_path / "nonexistent")
    assert result == []
    assert warnings == []


def test_invalid_thesis_json_produces_warning(tmp_path: Path):
    positions_dir = tmp_path / "_positions"
    ticker_dir = positions_dir / "KR_003550"
    ticker_dir.mkdir(parents=True)
    (ticker_dir / "thesis.json").write_text("{ invalid", encoding="utf-8")
    result, warnings = load_event_trigger_positions(positions_dir)
    assert result == []
    assert len(warnings) == 1


# ============================================================
# load_stage3_catalysts
# ============================================================

def test_missing_stage3_file_returns_warning(tmp_path: Path):
    catalysts, warnings = load_stage3_catalysts(tmp_path)
    assert catalysts == []
    assert len(warnings) == 1
    assert "Stage 3" in warnings[0]


def test_invalid_stage3_json_returns_warning(tmp_path: Path):
    p = tmp_path / "03-catalyst-events.json"
    p.write_text("{ not json", encoding="utf-8")
    catalysts, warnings = load_stage3_catalysts(tmp_path)
    assert catalysts == []
    assert len(warnings) == 1


def test_catalysts_and_orphans_flattened(tmp_path: Path):
    p = tmp_path / "03-catalyst-events.json"
    payload = {
        "schema": "investment-stage3-catalyst-events-v1",
        "catalysts": [_make_catalyst(ticker="KR:000001")],
        "d_type_orphans": [_make_catalyst(ticker="KR:000002", catalyst_type="treasury_share_cancellation")],
        "warnings": [],
    }
    p.write_text(json.dumps(payload), encoding="utf-8")
    catalysts, warnings = load_stage3_catalysts(tmp_path)
    assert len(catalysts) == 2
    assert warnings == []
    tickers = {c["ticker"] for c in catalysts}
    assert "KR:000001" in tickers
    assert "KR:000002" in tickers


def test_stage3_empty_arrays(tmp_path: Path):
    p = tmp_path / "03-catalyst-events.json"
    p.write_text(json.dumps({"catalysts": [], "d_type_orphans": []}), encoding="utf-8")
    catalysts, warnings = load_stage3_catalysts(tmp_path)
    assert catalysts == []
    assert warnings == []
