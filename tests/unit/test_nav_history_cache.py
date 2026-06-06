"""tests/unit/test_nav_history_cache.py — NAV cache + narrowing detector."""

from __future__ import annotations

from pathlib import Path

import pytest

from domains._shared import nav_history as nav_cache
from domains._shared.nav_history import (
    append_nav_snapshot,
    detect_narrowing,
    load_nav_history,
)

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def patch_cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """nav_history store 가 tmp_path 를 가리키도록 $NAV_HISTORY_DIR 격리.

    B-2 로 store 가 catalyst/io → domains/_shared/nav_history 이전, 경로는
    ``utils.nav_history_dir()`` (``$NAV_HISTORY_DIR`` env 우선) 가 해석한다.
    """
    monkeypatch.setenv("NAV_HISTORY_DIR", str(tmp_path))
    yield


class TestAppendAndLoad:
    def test_empty_initial_load(self) -> None:
        assert load_nav_history("KR:003550") == []

    def test_append_then_load(self) -> None:
        append_nav_snapshot(
            "KR:003550",
            "2026-05-09",
            parent_mcap_krw=12_000_000_000_000,
            nav_sum_krw=35_000_000_000_000,
            premium_pct=-0.6571,
            citations=["KIS@2026-05-09=12000000000000"],
        )
        out = load_nav_history("KR:003550")
        assert len(out) == 1
        assert out[0]["premium_pct"] == pytest.approx(-0.6571)

    def test_multiple_snapshots_sorted(self) -> None:
        for d, p in [("2026-05-09", -0.65), ("2026-05-01", -0.70), ("2026-05-05", -0.68)]:
            append_nav_snapshot(
                "KR:003550",
                d,
                parent_mcap_krw=1.0,
                nav_sum_krw=2.0,
                premium_pct=p,
            )
        out = load_nav_history("KR:003550")
        dates = [r["date"] for r in out]
        assert dates == sorted(dates)

    def test_lookback_truncate(self) -> None:
        for d, p in [("2026-01-01", -0.70), ("2026-04-01", -0.68), ("2026-05-01", -0.66)]:
            append_nav_snapshot("KR:003550", d, parent_mcap_krw=1.0, nav_sum_krw=2.0, premium_pct=p)
        # lookback 60일 → 2026-05-01 기준 -60일 = 2026-03-02 → 4-01 / 5-01 만
        out = load_nav_history("KR:003550", lookback_days=60)
        assert [r["date"] for r in out] == ["2026-04-01", "2026-05-01"]


class TestListParents:
    def test_empty_store(self) -> None:
        assert nav_cache.list_parents() == []

    def test_lists_parents_sorted_unique(self) -> None:
        append_nav_snapshot("KR:003550", "2026-05-01", parent_mcap_krw=1.0, nav_sum_krw=2.0, premium_pct=-0.5)
        append_nav_snapshot("KR:003550", "2026-05-02", parent_mcap_krw=1.0, nav_sum_krw=2.0, premium_pct=-0.4)
        append_nav_snapshot("KR:000880", "2026-05-01", parent_mcap_krw=1.0, nav_sum_krw=2.0, premium_pct=-0.5)
        assert nav_cache.list_parents() == ["KR:000880", "KR:003550"]


class TestDetectNarrowing:
    def test_insufficient_history(self) -> None:
        assert detect_narrowing([], -0.05) is None
        assert detect_narrowing([{"premium_pct": -0.7, "date": "2026-05-01"}], -0.05) is None

    def test_no_narrowing(self) -> None:
        # premium 7%p 좁힘 < threshold 10%p → None
        history = [
            {"date": "2026-05-01", "premium_pct": -0.70},
            {"date": "2026-05-09", "premium_pct": -0.63},
        ]
        assert detect_narrowing(history, -0.10) is None

    def test_narrowing_detected(self) -> None:
        # premium 12%p 좁힘 ≥ threshold 5%p → trigger
        history = [
            {"date": "2026-05-01", "premium_pct": -0.70, "citations": ["A"]},
            {"date": "2026-05-09", "premium_pct": -0.58, "citations": ["B"]},
        ]
        out = detect_narrowing(history, -0.05)
        assert out is not None
        assert out["delta"] == pytest.approx(0.12)
        assert out["earliest_date"] == "2026-05-01"
        assert out["latest_date"] == "2026-05-09"
        assert "A" in out["citations"] and "B" in out["citations"]

    def test_widening_not_triggered(self) -> None:
        # premium 더 음수 (할인 확대) → delta < 0 → None
        history = [
            {"date": "2026-05-01", "premium_pct": -0.55},
            {"date": "2026-05-09", "premium_pct": -0.70},
        ]
        assert detect_narrowing(history, -0.05) is None

    def test_invalid_premium_returns_none(self) -> None:
        history = [
            {"date": "2026-05-01", "premium_pct": "not a number"},
            {"date": "2026-05-09", "premium_pct": -0.55},
        ]
        assert detect_narrowing(history, -0.05) is None
