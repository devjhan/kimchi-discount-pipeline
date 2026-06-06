"""tests/unit/test_sizing.py — domains.risk_engine.sizing pure-fn tests."""

from __future__ import annotations

import pytest

from domains.risk_engine.sizing import (
    compute_fractional_kelly,
    extract_asymmetry_ratio,
    parse_pct,
)

pytestmark = pytest.mark.unit


class TestParsePct:
    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("-30%", 0.30),
            ("+120%", 1.20),
            ("50%", 0.50),
            ("-0.5%", 0.005),
            ("0%", 0.0),
        ],
    )
    def test_valid_percentages(self, raw: str, expected: float) -> None:
        assert parse_pct(raw) == pytest.approx(expected)

    @pytest.mark.parametrize("raw", [None, "", "abc", "30", "30 percent", "%50"])
    def test_invalid_inputs_return_none(self, raw) -> None:
        assert parse_pct(raw) is None


class TestExtractAsymmetryRatio:
    def test_normal_ratio(self) -> None:
        asym = {
            "downside_floor": {"krw_per_share_or_pct": "-25%"},
            "upside_ceiling": {"krw_per_share_or_pct": "+80%"},
        }
        ratio, err = extract_asymmetry_ratio(asym)
        assert err is None
        assert ratio == pytest.approx(80 / 25, rel=1e-3)

    def test_downside_zero_returns_error(self) -> None:
        asym = {
            "downside_floor": {"krw_per_share_or_pct": "0%"},
            "upside_ceiling": {"krw_per_share_or_pct": "+50%"},
        }
        ratio, err = extract_asymmetry_ratio(asym)
        assert ratio is None
        assert err is not None and "Kelly 정의 안 됨" in err

    def test_missing_field_returns_error(self) -> None:
        # 100억 KRW 절대값은 1차 미지원 → parse_pct fail → None
        asym = {
            "downside_floor": {"krw_per_share_or_pct": "10000원"},
            "upside_ceiling": {"krw_per_share_or_pct": "+50%"},
        }
        ratio, err = extract_asymmetry_ratio(asym)
        assert ratio is None
        assert err is not None and "asymmetry parse fail" in err

    def test_empty_dict(self) -> None:
        ratio, err = extract_asymmetry_ratio({})
        assert ratio is None and err is not None


class TestComputeFractionalKelly:
    def test_positive_edge(self) -> None:
        # b=2 (asymmetry_ratio), p=0.5, q=0.5 → f* = 0.5 - 0.25 = 0.25
        # quarter-Kelly fraction=0.25 → 0.0625
        out = compute_fractional_kelly(2.0, 0.25)
        assert out == pytest.approx(0.0625, rel=1e-3)

    def test_no_edge_returns_zero(self) -> None:
        # b=0.5 → f*=0.5 - 1.0 = -0.5 → 0
        assert compute_fractional_kelly(0.5, 0.25) == 0.0

    def test_high_edge(self) -> None:
        # b=4, p=0.5, q=0.5 → f*=0.5 - 0.125 = 0.375 → ×0.5 fraction = 0.1875
        out = compute_fractional_kelly(4.0, 0.5)
        assert out == pytest.approx(0.1875, rel=1e-3)
