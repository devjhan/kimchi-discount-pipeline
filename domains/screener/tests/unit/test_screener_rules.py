"""Rule 트리 단위 테스트 — leaf/composite 동작 + HardGuardWrapper + factory."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from domains.screener.domain.ticker import FilingMetric, TickerSnapshot
from domains.screener.errors import HardGuardViolationError
from domains.screener.rules.composite import AndRule, OrRule, WeightedSumRule
from domains.screener.rules.factory import RuleFactory
from domains.screener.rules.guards import HardGuardWrapper
from domains.screener.rules.leaf import ScoringRule, SignalPresenceRule, ThresholdRule
from domains._shared.time.clock import AsOfClock

KST = timezone(timedelta(hours=9))


def _snap(*, op_income: float = 120.0, debt: float = 400.0,
          equity: float = 1000.0, finance_costs: float = 10.0,
          signals: tuple[str, ...] = ()) -> TickerSnapshot:
    clock = AsOfClock.at_market_close(date(2026, 5, 15))
    filings = tuple(
        FilingMetric(
            fiscal_period=f"{2023 + i}Y",
            period_end_date=date(2023 + i, 12, 31),
            filing_datetime=datetime(2024 + i, 3, 15, 18, 0, tzinfo=KST),
            kind="annual",
            is_amended=False,
            revenue=1000.0,
            operating_income=op_income,
            total_assets=2000.0,
            total_equity=equity,
            total_debt=debt,
            finance_costs=finance_costs,
            operating_cash_flow=150.0,
            capex=50.0,
            citation=f"DART@{2024 + i}-03-15T18:00:00+09:00={{}}",
        )
        for i in range(3)
    )
    return TickerSnapshot(
        ticker="KR:000001",
        name="테스트",
        clock=clock,
        annuals=filings,
        capital_allocation_signals=signals,
    )


@pytest.mark.unit
def test_threshold_pass() -> None:
    rule = ThresholdRule(
        _name="ic_floor",
        metric_path="latest_annual.interest_coverage",
        op="ge",
        threshold=4.0,
    )
    r = rule.evaluate(_snap())
    assert r.passed
    assert r.score == 1.0


@pytest.mark.unit
def test_threshold_fail() -> None:
    rule = ThresholdRule(
        _name="ic_floor",
        metric_path="latest_annual.interest_coverage",
        op="ge",
        threshold=20.0,
    )
    r = rule.evaluate(_snap())
    assert not r.passed
    assert r.reasons


@pytest.mark.unit
def test_scoring_piecewise_linear() -> None:
    rule = ScoringRule(
        _name="de_score",
        metric_path="latest_annual.debt_to_equity",
        method="piecewise_linear",
        params={"floor": 1.0, "target": 0.3, "direction": "lower_is_better"},
        pass_score=0.5,
    )
    r = rule.evaluate(_snap(debt=400.0, equity=1000.0))  # D/E = 0.4
    assert r.passed
    assert r.score > 0.5


@pytest.mark.unit
def test_signal_presence() -> None:
    rule = SignalPresenceRule(
        _name="payout",
        required_any_of=("dividend_payment", "treasury_share_cancellation"),
    )
    assert rule.evaluate(_snap(signals=("dividend_payment",))).passed
    assert not rule.evaluate(_snap(signals=())).passed


@pytest.mark.unit
def test_and_rule_short_circuit_via_score() -> None:
    pass_rule = ThresholdRule(
        _name="a", metric_path="latest_annual.interest_coverage",
        op="ge", threshold=4.0,
    )
    fail_rule = ThresholdRule(
        _name="b", metric_path="latest_annual.debt_to_equity",
        op="le", threshold=0.1,
    )
    rule = AndRule(_name="ab", children=(pass_rule, fail_rule))
    r = rule.evaluate(_snap())
    assert not r.passed
    assert r.score == 0.0


@pytest.mark.unit
def test_or_rule_passes_when_one_child_passes() -> None:
    pass_rule = ThresholdRule(
        _name="a", metric_path="latest_annual.interest_coverage",
        op="ge", threshold=4.0,
    )
    fail_rule = ThresholdRule(
        _name="b", metric_path="latest_annual.debt_to_equity",
        op="le", threshold=0.1,
    )
    rule = OrRule(_name="ab", children=(pass_rule, fail_rule))
    assert rule.evaluate(_snap()).passed


@pytest.mark.unit
def test_weighted_sum_passes_when_average_meets_threshold() -> None:
    high = ScoringRule(
        _name="high",
        metric_path="latest_annual.interest_coverage",
        method="piecewise_linear",
        params={"floor": 0.0, "target": 10.0},
        pass_score=0.5,
    )
    low = ScoringRule(
        _name="low",
        metric_path="latest_annual.debt_to_equity",
        method="piecewise_linear",
        params={"floor": 1.0, "target": 0.0, "direction": "lower_is_better"},
        pass_score=0.5,
    )
    rule = WeightedSumRule(
        _name="combo",
        children=((high, 0.7), (low, 0.3)),
        pass_score=0.4,
    )
    r = rule.evaluate(_snap())
    assert r.passed
    assert 0 < r.score <= 1.0


@pytest.mark.unit
def test_hard_guard_wrapper_blocks_when_guard_fails() -> None:
    inner = ThresholdRule(
        _name="inner_pass",
        metric_path="latest_annual.interest_coverage",
        op="ge", threshold=4.0,
    )
    guard = ThresholdRule(
        _name="ic_hard_floor",
        metric_path="latest_annual.interest_coverage",
        op="ge", threshold=100.0,
    )
    wrapper = HardGuardWrapper(
        _name="strategy[test]", inner=inner, guards=(guard,),
    )
    r = wrapper.evaluate(_snap())
    assert not r.passed
    assert any(reason.startswith("HARD_FLOOR:") for reason in r.reasons)
    assert r.has_hard_floor_violation


@pytest.mark.unit
def test_hard_guard_wrapper_passes_when_guards_pass() -> None:
    inner = ThresholdRule(
        _name="inner_pass",
        metric_path="latest_annual.interest_coverage",
        op="ge", threshold=4.0,
    )
    guard = ThresholdRule(
        _name="ic_hard_floor",
        metric_path="latest_annual.interest_coverage",
        op="ge", threshold=1.5,
    )
    wrapper = HardGuardWrapper(
        _name="strategy[test]", inner=inner, guards=(guard,),
    )
    assert wrapper.evaluate(_snap()).passed


@pytest.mark.unit
def test_factory_builds_strategy_with_outer_guard() -> None:
    strategy = {
        "name": "test_strategy",
        "rule": {
            "type": "threshold",
            "name": "inner_check",
            "metric_path": "latest_annual.interest_coverage",
            "op": "ge",
            "threshold": 4.0,
        },
    }
    hard_guards = {
        "guards": [
            {
                "type": "threshold",
                "name": "solvency_floor",
                "metric_path": "latest_annual.interest_coverage",
                "op": "ge",
                "threshold": 1.5,
            }
        ],
        "locked_paths": ["guards.*"],
    }
    rule = RuleFactory.build_strategy(strategy, profiles={}, hard_guards=hard_guards)
    assert isinstance(rule, HardGuardWrapper)
    assert rule.evaluate(_snap()).passed


@pytest.mark.unit
def test_factory_rejects_hard_guard_name_override() -> None:
    strategy = {
        "name": "evil",
        "rule": {
            "type": "threshold",
            "name": "solvency_floor",  # 의도적 충돌
            "metric_path": "latest_annual.interest_coverage",
            "op": "ge",
            "threshold": 0.001,
        },
    }
    hard_guards = {
        "guards": [
            {
                "type": "threshold",
                "name": "solvency_floor",
                "metric_path": "latest_annual.interest_coverage",
                "op": "ge",
                "threshold": 1.5,
            }
        ],
        "locked_paths": ["guards.*"],
    }
    with pytest.raises(HardGuardViolationError):
        RuleFactory.build_strategy(strategy, profiles={}, hard_guards=hard_guards)


@pytest.mark.unit
def test_scoring_rule_params_immutable() -> None:
    """MEDIUM 결함 cover — ScoringRule.params 가 mutable dict 였던 문제 회귀 방지."""
    rule = ScoringRule(
        _name="x",
        metric_path="latest_annual.interest_coverage",
        method="piecewise_linear",
        params={"floor": 0.0, "target": 10.0},
        pass_score=0.5,
    )
    with pytest.raises(TypeError):
        rule.params["floor"] = 999.0  # type: ignore[index]
    # dict() 변환 통해서는 freely mutable — 보안 책임은 호출자 측
    copy = dict(rule.params)
    copy["floor"] = 999.0
    assert rule.params["floor"] == 0.0  # 원본은 그대로


@pytest.mark.unit
def test_factory_rejects_unknown_method() -> None:
    strategy = {
        "name": "evil",
        "rule": {
            "type": "scoring",
            "name": "bad",
            "metric_path": "latest_annual.interest_coverage",
            "method": "nonexistent",
            "params": {},
            "pass_score": 0.5,
        },
    }
    hard_guards = {"guards": [], "locked_paths": []}
    with pytest.raises(ValueError):
        RuleFactory.build_strategy(strategy, profiles={}, hard_guards=hard_guards)
