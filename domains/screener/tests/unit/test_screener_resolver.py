"""resolver 화이트리스트 단위 테스트 — 등록된 metric 만 허용, dynamic eval 차단."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from domains.screener.domain.ticker import FilingMetric, TickerSnapshot
from domains.screener.errors import InsufficientHistoryError, MetricResolutionError
from domains.screener.rules.leaf import ThresholdRule
from domains.screener.rules.resolver import resolve_metric
from domains._shared.time.clock import AsOfClock

KST = timezone(timedelta(hours=9))


def _make_snapshot() -> TickerSnapshot:
    clock = AsOfClock.at_market_close(date(2026, 5, 15))
    filings = tuple(
        FilingMetric(
            fiscal_period=f"{2023 + i}Y",
            period_end_date=date(2023 + i, 12, 31),
            filing_datetime=datetime(2024 + i, 3, 15, 18, 0, tzinfo=KST),
            kind="annual",
            is_amended=False,
            revenue=1000.0,
            operating_income=120.0,
            total_assets=2000.0,
            total_equity=1000.0,
            total_debt=400.0,
            finance_costs=10.0,
            operating_cash_flow=150.0,
            capex=50.0,
            citation=f"DART@{2024 + i}-03-15T18:00:00+09:00={{}}",
        )
        for i in range(3)
    )
    return TickerSnapshot(
        ticker="KR:000001",
        name="테스트종목",
        clock=clock,
        annuals=filings,
        capital_allocation_signals=("dividend_payment",),
    )


@pytest.mark.unit
def test_unknown_metric_raises() -> None:
    snap = _make_snapshot()
    with pytest.raises(MetricResolutionError):
        resolve_metric(snap, "nonexistent.metric")


@pytest.mark.unit
def test_roic_requires_tax_rate() -> None:
    snap = _make_snapshot()
    with pytest.raises(MetricResolutionError):
        resolve_metric(snap, "annuals_avg.roic", period_years=3)


@pytest.mark.unit
def test_roic_computes() -> None:
    snap = _make_snapshot()
    # NOPAT = 120 * (1 - 0.22) = 93.6, invested = 1400, ROIC = 0.0668...
    v = resolve_metric(snap, "annuals_avg.roic", period_years=3, tax_rate=0.22)
    assert 0.06 < v < 0.07


@pytest.mark.unit
def test_debt_to_equity() -> None:
    snap = _make_snapshot()
    v = resolve_metric(snap, "latest_annual.debt_to_equity")
    assert v == pytest.approx(0.4)


@pytest.mark.unit
def test_interest_coverage() -> None:
    snap = _make_snapshot()
    v = resolve_metric(snap, "latest_annual.interest_coverage")
    assert v == pytest.approx(12.0)


@pytest.mark.unit
def test_fcf_positive_years() -> None:
    snap = _make_snapshot()
    v = resolve_metric(snap, "fcf_positive_years", period_years=3)
    assert v == 3.0


@pytest.mark.unit
def test_signals_count() -> None:
    snap = _make_snapshot()
    v = resolve_metric(snap, "signals.count")
    assert v == 1.0


@pytest.mark.unit
def test_insufficient_history() -> None:
    clock = AsOfClock.at_market_close(date(2026, 5, 15))
    snap = TickerSnapshot(ticker="KR:X", name="X", clock=clock, annuals=())
    with pytest.raises(InsufficientHistoryError):
        resolve_metric(snap, "annuals_avg.roic", period_years=3, tax_rate=0.22)


# ----------------------------------------------------------------------
# Step 4.1 (B) — enrichments.<group>.<key> 화이트리스트 분기
# ----------------------------------------------------------------------


def _snap_with_enrichments(enrichments) -> TickerSnapshot:
    clock = AsOfClock.at_market_close(date(2026, 5, 15))
    return TickerSnapshot(
        ticker="KR:000001", name="X", clock=clock, annuals=(), enrichments=enrichments
    )


@pytest.mark.unit
def test_enrichment_path_resolves() -> None:
    snap = _snap_with_enrichments({"nav_discount": {"discount_pct": 0.25}})
    assert resolve_metric(snap, "enrichments.nav_discount.discount_pct") == 0.25


@pytest.mark.unit
def test_enrichment_bool_coerces_to_float() -> None:
    """catalyst_flag (bool) → 1.0/0.0."""
    snap = _snap_with_enrichments({"spread_zscore": {"catalyst_flag": True}})
    assert resolve_metric(snap, "enrichments.spread_zscore.catalyst_flag") == 1.0


@pytest.mark.unit
def test_non_whitelisted_enrichment_raises() -> None:
    snap = _snap_with_enrichments({"foo": {"bar": 1.0}})
    with pytest.raises(MetricResolutionError):
        resolve_metric(snap, "enrichments.foo.bar")


@pytest.mark.unit
def test_malformed_path_raises() -> None:
    """enrichments.<group> (키 없음) → 형식 위반."""
    snap = _snap_with_enrichments({"nav_discount": {"discount_pct": 0.25}})
    with pytest.raises(MetricResolutionError):
        resolve_metric(snap, "enrichments.nav_discount")


@pytest.mark.unit
def test_threshold_rule_on_enrichment() -> None:
    rule = ThresholdRule(
        _name="nav_floor",
        metric_path="enrichments.nav_discount.discount_pct",
        op="ge",
        threshold=0.20,
    )
    assert rule.evaluate(
        _snap_with_enrichments({"nav_discount": {"discount_pct": 0.25}})
    ).passed is True
    assert rule.evaluate(
        _snap_with_enrichments({"nav_discount": {"discount_pct": 0.10}})
    ).passed is False


@pytest.mark.unit
def test_missing_enrichment_data_is_fail_not_pass() -> None:
    """group 부재 → leaf passed=False, reasons 에 data_missing (false pass 방지)."""
    rule = ThresholdRule(
        _name="nav_floor",
        metric_path="enrichments.nav_discount.discount_pct",
        op="ge",
        threshold=0.20,
    )
    result = rule.evaluate(_snap_with_enrichments({}))
    assert result.passed is False
    assert any("data_missing" in r for r in result.reasons)
