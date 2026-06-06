"""tests/unit/test_falsifier_proximity.py — domains.risk_engine.falsifier_proximity."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from domains.risk_engine.falsifier_proximity import (
    DEFAULT_PROXIMITY_BANDS,
    ProximityRecord,
    _months_between,
    load_open_positions,
    measure_proximity,
    render_drift_md,
)

pytestmark = pytest.mark.unit

BANDS = DEFAULT_PROXIMITY_BANDS


class TestMonthsBetween:
    def test_one_month(self) -> None:
        assert _months_between("2026-01-15", "2026-02-15") == pytest.approx(1.02, rel=0.05)

    def test_one_year(self) -> None:
        assert _months_between("2025-05-09", "2026-05-09") == pytest.approx(12.0, rel=0.02)

    def test_zero_days(self) -> None:
        assert _months_between("2026-05-09", "2026-05-09") == pytest.approx(0.0)


class TestMeasureProximityTimeCap:
    def _pos(self, entry_date: str, horizon_months: int) -> dict:
        return {
            "ticker": "KR:003550",
            "name": "LG",
            "entry_date": entry_date,
            "thesis": {
                "time_horizon_months": horizon_months,
                "falsifier": {"category": "time_cap"},
            },
        }

    def test_just_entered_proximity_low(self) -> None:
        # entry 5일 전, horizon 12개월 → elapsed/horizon ≈ 0.014 → ratio ≈ 0.986 → low
        pos = self._pos("2026-05-04", 12)
        rec = measure_proximity(pos, today="2026-05-09", bands=BANDS)
        assert rec.proximity == "low"
        assert rec.distance_ratio is not None and rec.distance_ratio > 0.9

    def test_halfway_proximity_medium(self) -> None:
        # ~8개월 경과, horizon 12개월 → elapsed/horizon ≈ 0.68 → inverse ≈ 0.68 → medium
        pos = self._pos("2025-09-01", 12)
        rec = measure_proximity(pos, today="2026-05-09", bands=BANDS)
        assert rec.proximity == "medium"

    def test_near_horizon_proximity_high(self) -> None:
        # 11.5개월 경과, horizon 12개월 → elapsed/horizon ≈ 0.96 → inverse ≈ 0.96 → high
        pos = self._pos("2025-05-22", 12)
        rec = measure_proximity(pos, today="2026-05-09", bands=BANDS)
        assert rec.proximity == "high"
        assert rec.needs_user_decision is True

    def test_horizon_zero(self) -> None:
        pos = self._pos("2026-01-01", 0)
        rec = measure_proximity(pos, today="2026-05-09", bands=BANDS)
        assert rec.proximity == "unmeasurable"

    def test_missing_horizon(self) -> None:
        pos = {
            "ticker": "X",
            "entry_date": "2026-01-01",
            "thesis": {"falsifier": {"category": "time_cap"}},
        }
        rec = measure_proximity(pos, today="2026-05-09", bands=BANDS)
        assert rec.proximity == "unmeasurable"


class TestMeasureProximityMetricTrigger:
    def _pos(self, target: float, baseline: float, direction: str = "below") -> dict:
        return {
            "ticker": "KR:005930",
            "name": "삼성전자",
            "entry_price_krw": 80000,
            "thesis": {
                "falsifier": {
                    "category": "metric_trigger",
                    "spec": {
                        "metric": "price",
                        "target_value": target,
                        "baseline_value": baseline,
                        "direction": direction,
                    },
                },
            },
        }

    def test_no_market_snapshot_unmeasurable(self) -> None:
        pos = self._pos(target=60000, baseline=80000)
        rec = measure_proximity(pos, today="2026-05-09", bands=BANDS)
        assert rec.proximity == "unmeasurable"

    def test_price_far_from_target_low(self) -> None:
        pos = self._pos(target=60000, baseline=80000)  # below trigger at 60000
        snap = {"KR:005930": {"price_krw": 78000, "source": "Yahoo", "ts": "2026-05-09"}}
        rec = measure_proximity(pos, today="2026-05-09", bands=BANDS, market_snapshot=snap)
        # gap = |78000-60000| = 18000, denom = 20000, ratio = 0.9 → inverse=0.1 → low
        assert rec.proximity == "low"

    def test_price_at_trigger_high(self) -> None:
        pos = self._pos(target=60000, baseline=80000)
        snap = {"KR:005930": {"price_krw": 60000, "source": "Yahoo", "ts": "2026-05-09"}}
        rec = measure_proximity(pos, today="2026-05-09", bands=BANDS, market_snapshot=snap)
        assert rec.proximity == "high"
        assert rec.distance_ratio == 0.0

    def test_price_below_trigger_clamps_to_high(self) -> None:
        pos = self._pos(target=60000, baseline=80000)
        snap = {"KR:005930": {"price_krw": 55000, "source": "Yahoo", "ts": "2026-05-09"}}
        rec = measure_proximity(pos, today="2026-05-09", bands=BANDS, market_snapshot=snap)
        assert rec.proximity == "high"
        assert rec.distance_ratio == 0.0


class TestMeasureProximityEventTrigger:
    def test_event_trigger_unmeasurable(self) -> None:
        pos = {
            "ticker": "KR:003550",
            "thesis": {"falsifier": {"category": "event_trigger", "spec": {}}},
        }
        rec = measure_proximity(pos, today="2026-05-09", bands=BANDS)
        assert rec.proximity == "unmeasurable"
        assert "Stage 3 catalyst-scan" in rec.rationale


class TestRenderDriftMd:
    def test_basic_render(self) -> None:
        rec = ProximityRecord(
            ticker="KR:003550",
            name="LG",
            proximity="medium",
            distance_ratio=0.45,
            rationale="time_cap: 6.5개월 경과 / horizon 12개월",
            falsifier_category="time_cap",
            citations=["POSITION@2026-01-01->2026-05-09={\"elapsed_months\":4.27}"],
        )
        body = render_drift_md(rec, today="2026-05-09")
        assert "# Falsifier Drift — KR:003550 LG" in body
        assert "**medium**" in body
        assert "G9" in body  # 자동 매매 disclaimer

    def test_high_proximity_shows_warning(self) -> None:
        rec = ProximityRecord(
            ticker="X",
            name="X",
            proximity="high",
            distance_ratio=0.05,
            rationale="...",
            falsifier_category="time_cap",
            needs_user_decision=True,
        )
        body = render_drift_md(rec, today="2026-05-09")
        assert "needs_user_decision" in body


class TestLoadOpenPositions:
    def test_empty_dir(self, tmp_path: Path) -> None:
        assert load_open_positions(tmp_path) == []

    def test_one_thesis(self, tmp_path: Path) -> None:
        sub = tmp_path / "KR_003550"
        sub.mkdir()
        (sub / "thesis.json").write_text(
            json.dumps({"ticker": "KR:003550", "name": "LG", "status": "open"})
        )
        out = load_open_positions(tmp_path)
        assert len(out) == 1 and out[0]["ticker"] == "KR:003550"

    def test_closed_position_excluded(self, tmp_path: Path) -> None:
        sub = tmp_path / "KR_005930"
        sub.mkdir()
        (sub / "thesis.json").write_text(
            json.dumps({"ticker": "KR:005930", "status": "closed"})
        )
        assert load_open_positions(tmp_path) == []

    def test_broken_json_skipped(self, tmp_path: Path) -> None:
        sub = tmp_path / "KR_BAD"
        sub.mkdir()
        (sub / "thesis.json").write_text("not valid")
        assert load_open_positions(tmp_path) == []
