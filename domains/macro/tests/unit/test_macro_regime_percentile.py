"""tests/unit/test_macro_regime_percentile.py — percentile pure-fn test.

Run 7: `domains.risk_engine.macro_regime._percentile` →
`domains.macro.indicators._percentile`.
F-9: `domains.macro.indicators._percentile` → `domains.macro.signals._stats.percentile`.
"""

from __future__ import annotations

import pytest

from domains.macro.signals._stats import percentile as _percentile

pytestmark = pytest.mark.unit


class TestPercentile:
    def test_empty_returns_none(self) -> None:
        assert _percentile([], 10.0) is None

    def test_target_below_min(self) -> None:
        assert _percentile([10.0, 20.0, 30.0], 5.0) == pytest.approx(0.0)

    def test_target_above_max(self) -> None:
        assert _percentile([10.0, 20.0, 30.0], 100.0) == pytest.approx(1.0)

    def test_target_in_middle(self) -> None:
        # samples=[10,20,30,40,50], target=25 → less=2 (10,20) → 0.4
        assert _percentile([10.0, 20.0, 30.0, 40.0, 50.0], 25.0) == pytest.approx(0.4)

    def test_target_equals_max(self) -> None:
        # less = all (<=), so percentile = 1.0
        assert _percentile([10.0, 20.0, 30.0], 30.0) == pytest.approx(1.0)
