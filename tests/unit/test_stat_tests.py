"""tests/unit/test_stat_tests.py — domains.audit_integrity.stat_tests."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from domains.audit_integrity.stat_tests import (
    bootstrap_ci,
    evaluate_self_disable_trigger,
    quarterly_returns,
    welch_t_test,
)

pytestmark = pytest.mark.unit


class TestWelchTTest:
    def test_insufficient_sample(self) -> None:
        out = welch_t_test([1.0], [2.0, 3.0])
        assert out["t"] is None
        assert out["p_two_sided"] is None
        assert "insufficient sample" in (out.get("note") or "")

    def test_identical_samples_diff_zero(self) -> None:
        a = [1.0, 2.0, 3.0, 4.0]
        out = welch_t_test(a, a)
        assert out["mean_diff"] == pytest.approx(0.0)
        assert out["t"] == pytest.approx(0.0)

    def test_known_diff_sign(self) -> None:
        # a 평균 < b 평균 → t < 0
        a = [0.01, 0.02, 0.01, 0.015]
        b = [0.04, 0.05, 0.045, 0.05]
        out = welch_t_test(a, b)
        assert out["t"] < 0
        assert out["mean_diff"] < 0

    def test_zero_variance_degenerate_path(self) -> None:
        # var_a == var_b == 0 → degenerate path (df 산출 불가, se_diff=0)
        out = welch_t_test([0.01] * 50, [0.02] * 50)
        assert out["se_diff"] == 0.0
        assert "degenerate" in (out.get("note") or "")

    def test_normal_approx_p_value(self) -> None:
        # 분산 있는 50쌍 → p-value 산출
        rng = [(i % 5) * 0.01 for i in range(50)]
        a = [v + 0.0 for v in rng]
        b = [v + 0.05 for v in rng]
        out = welch_t_test(a, b)
        assert out["p_two_sided"] is not None
        assert 0.0 <= out["p_two_sided"] <= 1.0
        assert out["ci_95"] is not None and len(out["ci_95"]) == 2

    def test_welch_formula_matches_hand_calc(self) -> None:
        # Hand-calc: a=[2,4], b=[6,8], n=2 each
        # mean_a=3, mean_b=7, mean_diff=-4
        # var_a=2, var_b=2, se_a=1, se_b=1, se_diff=sqrt(2)
        # t = -4 / sqrt(2) ≈ -2.828
        out = welch_t_test([2.0, 4.0], [6.0, 8.0])
        assert out["mean_diff"] == pytest.approx(-4.0)
        assert out["se_diff"] == pytest.approx(math.sqrt(2), rel=1e-3)
        assert out["t"] == pytest.approx(-4.0 / math.sqrt(2), rel=1e-3)


class TestBootstrapCI:
    def test_insufficient_sample(self) -> None:
        out = bootstrap_ci([1.0], iters=100, seed=1)
        assert out["ci_low"] is None and out["ci_high"] is None

    def test_deterministic_seed(self) -> None:
        a = [0.01, -0.02, 0.03, -0.01, 0.02]
        out1 = bootstrap_ci(a, iters=2000, seed=42)
        out2 = bootstrap_ci(a, iters=2000, seed=42)
        assert out1 == out2

    def test_ci_brackets_sample_mean(self) -> None:
        a = [0.01, -0.02, 0.03, -0.01, 0.02, 0.0, 0.015, -0.005]
        out = bootstrap_ci(a, iters=2000, seed=42)
        assert out["ci_low"] <= out["mean"] <= out["ci_high"]


class TestQuarterlyReturns:
    def test_state_missing(self, tmp_path: Path) -> None:
        out = quarterly_returns(tmp_path / "missing.json", "tier_2_llm_filtered")
        assert out == []

    def test_legacy_plain_floats(self, tmp_path: Path) -> None:
        p = tmp_path / "state.json"
        p.write_text(
            json.dumps(
                {"tiers": {"tier_1_mechanical": {"quarterly_history": [0.01, 0.02, 0.03]}}}
            )
        )
        assert quarterly_returns(p, "tier_1_mechanical") == [0.01, 0.02, 0.03]

    def test_dict_form_with_return_pct(self, tmp_path: Path) -> None:
        p = tmp_path / "state.json"
        p.write_text(
            json.dumps(
                {
                    "tiers": {
                        "tier_2_llm_filtered": {
                            "quarterly_history": [
                                {"quarter": "2026-Q1", "return_pct": 0.018},
                                {"quarter": "2026-Q2", "return_pct": 0.022},
                            ]
                        }
                    }
                }
            )
        )
        out = quarterly_returns(p, "tier_2_llm_filtered")
        assert out == [0.018, 0.022]

    def test_n_quarters_truncate(self, tmp_path: Path) -> None:
        p = tmp_path / "state.json"
        p.write_text(
            json.dumps(
                {"tiers": {"tier_3_random": {"quarterly_history": [0.01, 0.02, 0.03, 0.04]}}}
            )
        )
        assert quarterly_returns(p, "tier_3_random", n_quarters=2) == [0.03, 0.04]


class TestEvaluateSelfDisableTrigger:
    def test_sign_only_4_consecutive_no_p_value(self, sample_state: dict) -> None:
        out = evaluate_self_disable_trigger(sample_state)
        # sample_state: tier_2 모두 tier_1 보다 작음, n=4 이라 df<30
        assert out["consecutive_quarters"] == 4
        assert out["consec_passed_sign"] is True
        assert out["consec_passed_p"] is None  # df<30 → p None
        assert out["trigger_armed"] is False
        assert "사용자 명시 결정 필요" in out["rationale"]

    def test_sign_pattern_breaks_at_consec_3(self) -> None:
        state = {
            "tiers": {
                "tier_1_mechanical": {"quarterly_history": [0.04, 0.05, 0.03, 0.06]},
                "tier_2_llm_filtered": {"quarterly_history": [0.01, 0.02, 0.07, 0.04]},
                # 마지막 3분기 음수, but Q-3 (index 1, 0.02 < 0.05 → 음수)
                # 정확 확인: i=1 → a[-1]=0.04 < b[-1]=0.06 ✓
                #            i=2 → a[-2]=0.07 > b[-2]=0.03 ✗ → break
            }
        }
        out = evaluate_self_disable_trigger(state)
        assert out["consecutive_quarters"] == 1
        assert out["trigger_armed"] is False

    def test_no_history_returns_zero_consec(self) -> None:
        out = evaluate_self_disable_trigger({"tiers": {}})
        assert out["consecutive_quarters"] == 0
        assert out["trigger_armed"] is False
