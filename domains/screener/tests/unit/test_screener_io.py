"""screener io 모듈 단위 테스트.

- LiveFinancialCache: v3 호환 → snapshot=None, v4 write/read round-trip
- dart_adapter: _pick_account / _extract_3y / build_filings / _classify_signal
- capital_signals_cache: filter_visible_signals / merge_signal_events
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from domains.screener.domain.ticker import FilingMetric
from domains.screener.io import dart_adapter as _adapter
from domains.screener.io.capital_signals_cache import (
    filter_visible_signals,
    merge_signal_events,
)
from domains.screener.io.financial_cache import (
    CachePolicy,
    LiveFinancialCache,
    policy_from_strategy,
)
from domains._shared.time.clock import AsOfClock

KST = timezone(timedelta(hours=9))


@pytest.fixture(autouse=True)
def _freeze_kst_today(monkeypatch: pytest.MonkeyPatch) -> None:
    """LiveFinancialCache.get_snapshot 의 today 검증 우회 — test fixture 의 clock 과 동기화."""
    from domains.screener import _boundary

    fixed = datetime(2026, 5, 15, 15, 30, tzinfo=KST)
    monkeypatch.setattr(_boundary, "now_kst", lambda: fixed)


# ----------------------------------------------------------------------
# LiveFinancialCache
# ----------------------------------------------------------------------


@pytest.fixture
def policy() -> CachePolicy:
    return CachePolicy(
        financials_ttl_days=30,
        capital_signals_ttl_days=7,
        staleness_grace_days=14,
    )


@pytest.mark.unit
def test_non_v4_schema_treated_as_miss(tmp_path: Path, policy: CachePolicy) -> None:
    """schema 가 v4 가 아니면 cache miss (legacy / unknown 모두)."""
    cache_dir = tmp_path / "financials"
    cache_dir.mkdir()
    legacy = cache_dir / "KR_TEST.json"
    legacy.write_text(
        json.dumps(
            {
                "schema": "investment-stage2-fin-cache-v3",
                "ticker": "KR:TEST",
                "metrics": {"roic_annual": [0.1]},
            },
            ensure_ascii=False,
        )
    )

    cache = LiveFinancialCache(base_dir=cache_dir, policy=policy)
    clock = AsOfClock.at_market_close(date(2026, 5, 15))
    assert cache.get_snapshot("KR:TEST", "테스트", clock) is None


@pytest.mark.unit
def test_live_cache_rejects_past_clock(
    tmp_path: Path, policy: CachePolicy, monkeypatch: pytest.MonkeyPatch
) -> None:
    """MEDIUM 결함 cover — LiveFinancialCache 가 과거 clock 받으면 ValueError."""
    from domains.screener import _boundary

    fixed = datetime(2026, 5, 15, 15, 30, tzinfo=KST)
    monkeypatch.setattr(_boundary, "now_kst", lambda: fixed)
    cache = LiveFinancialCache(base_dir=tmp_path / "financials", policy=policy)
    past_clock = AsOfClock.at_market_close(date(2024, 1, 15))
    with pytest.raises(ValueError, match="LiveFinancialCache"):
        cache.get_snapshot("KR:X", "X", past_clock)


@pytest.mark.unit
def test_universe_citation_preserved_in_v4_roundtrip(
    tmp_path: Path, policy: CachePolicy
) -> None:
    """MEDIUM 결함 cover — universe_citation 이 write → read round-trip 에서 보존."""
    cache = LiveFinancialCache(base_dir=tmp_path / "financials", policy=policy)
    filings = [
        FilingMetric(
            fiscal_period="2024Y",
            period_end_date=date(2024, 12, 31),
            filing_datetime=datetime(2025, 3, 15, 18, 0, tzinfo=KST),
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
            citation="DART@2025-03-15T18:00:00+09:00={}",
        )
    ]
    cache.write_atomic(
        "KR:U",
        name="U",
        corp_code="00000000",
        bsns_year="2024",
        tax_rate=0.22,
        filings=filings,
        capital_signals_events=[],
        metrics={},
        citations=[],
        universe_citation="DART@2026-05-01T15:30=universe-cit",
    )
    snap = cache.get_snapshot("KR:U", "U", AsOfClock.at_market_close(date(2026, 5, 15)))
    assert snap is not None
    assert snap.universe_citation == "DART@2026-05-01T15:30=universe-cit"
    assert "DART@2026-05-01T15:30=universe-cit" in snap.all_citations()


@pytest.mark.unit
def test_v4_cache_roundtrip(tmp_path: Path, policy: CachePolicy) -> None:
    """v4 write → read → TickerSnapshot 복원이 정상."""
    cache_dir = tmp_path / "financials"
    cache_dir.mkdir()
    cache = LiveFinancialCache(base_dir=cache_dir, policy=policy)

    filings = [
        FilingMetric(
            fiscal_period="2024Y",
            period_end_date=date(2024, 12, 31),
            filing_datetime=datetime(2025, 3, 15, 18, 0, tzinfo=KST),
            kind="annual",
            is_amended=False,
            revenue=1000.0,
            operating_income=120.0,
            net_income=80.0,
            total_assets=2000.0,
            total_equity=1000.0,
            total_debt=400.0,
            finance_costs=10.0,
            operating_cash_flow=150.0,
            capex=50.0,
            citation="DART@2025-03-15T18:00:00+09:00={...}",
        )
    ]
    cache.write_atomic(
        "KR:TEST",
        name="테스트",
        corp_code="00112378",
        bsns_year="2024",
        tax_rate=0.22,
        filings=filings,
        capital_signals_events=[],
        metrics={"roic_annual": [0.0936]},
        citations=["DART@..."],
    )

    clock = AsOfClock.at_market_close(date(2026, 5, 15))
    snap = cache.get_snapshot("KR:TEST", "테스트", clock)
    assert snap is not None
    assert snap.ticker == "KR:TEST"
    assert len(snap.annuals) == 1
    assert snap.annuals[0].fiscal_period == "2024Y"
    assert snap.annuals[0].revenue == 1000.0


@pytest.mark.unit
def test_policy_from_strategy_uses_defaults() -> None:
    strategy_yaml = {"constants": {"financial_cache": {"financials_ttl_days": 45}}}
    p = policy_from_strategy(strategy_yaml)
    assert p.financials_ttl_days == 45
    assert p.capital_signals_ttl_days == 7  # default
    assert p.staleness_grace_days == 14


# ----------------------------------------------------------------------
# dart_adapter helpers
# ----------------------------------------------------------------------


def _dart_item(
    *,
    sj_div: str,
    account_id: str,
    account_nm: str,
    pp: str | None = None,
    p: str | None = None,
    t: str | None = None,
) -> dict[str, object]:
    return {
        "sj_div": sj_div,
        "account_id": account_id,
        "account_nm": account_nm,
        "bfefrmtrm_amount": pp,
        "frmtrm_amount": p,
        "thstrm_amount": t,
    }


@pytest.mark.unit
def test_pick_account_matches_by_id_first() -> None:
    items = [
        _dart_item(
            sj_div="IS",
            account_id="ifrs-full_Revenue",
            account_nm="매출액",
            t="1000",
        )
    ]
    item = _adapter._pick_account(
        items,
        sj_div="IS",
        names=("매출액",),
        account_ids=("ifrs-full_Revenue",),
    )
    assert item is not None
    assert item["account_id"] == "ifrs-full_Revenue"


@pytest.mark.unit
def test_pick_account_falls_back_to_nm() -> None:
    items = [
        _dart_item(
            sj_div="IS", account_id="", account_nm="매출액", t="500",
        )
    ]
    item = _adapter._pick_account(
        items,
        sj_div="IS",
        names=("매출액",),
        account_ids=("ifrs-full_Revenue",),
    )
    assert item is not None
    assert item["thstrm_amount"] == "500"


@pytest.mark.unit
def test_extract_3y_parses_commas() -> None:
    item = {
        "bfefrmtrm_amount": "1,000",
        "frmtrm_amount": "1,200",
        "thstrm_amount": "1,500",
    }
    pp, p, t = _adapter._extract_3y(item)
    assert (pp, p, t) == (1000.0, 1200.0, 1500.0)


@pytest.mark.unit
def test_extract_3y_none_safe() -> None:
    pp, p, t = _adapter._extract_3y(None)
    assert (pp, p, t) == (None, None, None)


@pytest.mark.unit
def test_build_filings_creates_3_years() -> None:
    items = [
        _dart_item(
            sj_div="IS",
            account_id="ifrs-full_Revenue",
            account_nm="매출액",
            pp="800", p="900", t="1000",
        ),
        _dart_item(
            sj_div="IS",
            account_id="dart_OperatingIncomeLoss",
            account_nm="영업이익",
            pp="80", p="100", t="120",
        ),
        _dart_item(
            sj_div="BS",
            account_id="ifrs-full_Equity",
            account_nm="자본총계",
            pp="900", p="950", t="1000",
        ),
        _dart_item(
            sj_div="BS",
            account_id="ifrs-full_Liabilities",
            account_nm="부채총계",
            pp="380", p="390", t="400",
        ),
    ]
    filings = _adapter.build_filings(
        items,
        bsns_year=2024,
        filing_datetime=datetime(2025, 3, 15, 18, 0, tzinfo=KST),
        citation="DART@2025-03-15T18:00:00+09:00={...}",
    )
    assert len(filings) == 3
    assert filings[0].fiscal_period == "2022Y"
    assert filings[-1].fiscal_period == "2024Y"
    assert filings[-1].revenue == 1000.0
    assert filings[-1].operating_income == 120.0


@pytest.mark.unit
def test_classify_signal_treasury_cancellation() -> None:
    assert _adapter._classify_signal("주요사항보고서(자기주식소각결정)") == "treasury_share_cancellation"
    assert _adapter._classify_signal("주요사항보고서(자기주식취득결정)") == "treasury_share_purchase"
    assert _adapter._classify_signal("주요사항보고서(현금배당결정)") == "dividend_payment"
    assert _adapter._classify_signal("기타") is None


@pytest.mark.unit
def test_determine_bsns_year_before_april() -> None:
    # 3월에는 작년 사업보고서 미발표 → 전전년도
    assert _adapter.determine_bsns_year(date(2026, 3, 15)) == 2024


@pytest.mark.unit
def test_determine_bsns_year_after_april() -> None:
    # 4월 이후 작년 사업보고서 가시
    assert _adapter.determine_bsns_year(date(2026, 5, 15)) == 2025


# ----------------------------------------------------------------------
# capital_signals_cache
# ----------------------------------------------------------------------


@pytest.mark.unit
def test_filter_visible_signals_clock_aware() -> None:
    events = [
        {
            "event_datetime": "2025-08-05T23:59:59+09:00",
            "signal_type": "treasury_share_purchase",
        },
        {
            "event_datetime": "2026-06-01T23:59:59+09:00",  # 미래
            "signal_type": "dividend_payment",
        },
    ]
    clock = AsOfClock.at_market_close(date(2026, 5, 15))
    visible = filter_visible_signals(events, clock)
    assert "treasury_share_purchase" in visible
    assert "dividend_payment" not in visible


@pytest.mark.unit
def test_filter_visible_signals_dedup() -> None:
    events = [
        {
            "event_datetime": "2025-08-05T23:59:59+09:00",
            "signal_type": "dividend_payment",
        },
        {
            "event_datetime": "2025-09-05T23:59:59+09:00",
            "signal_type": "dividend_payment",
        },
    ]
    clock = AsOfClock.at_market_close(date(2026, 5, 15))
    visible = filter_visible_signals(events, clock)
    assert visible == ("dividend_payment",)


@pytest.mark.unit
def test_merge_signal_events_dedup_and_sort() -> None:
    prev = [
        {
            "event_datetime": "2025-08-05T23:59:59+09:00",
            "signal_type": "dividend_payment",
        }
    ]
    new = [
        {
            "event_datetime": "2025-08-05T23:59:59+09:00",  # dup
            "signal_type": "dividend_payment",
            "rcept_no": "20250805000286",  # 새 metadata
        },
        {
            "event_datetime": "2025-09-05T23:59:59+09:00",
            "signal_type": "treasury_share_purchase",
        },
    ]
    merged = merge_signal_events(prev, new)
    assert len(merged) == 2
    assert merged[0]["event_datetime"] < merged[1]["event_datetime"]
    # new 의 metadata 우선
    assert merged[0].get("rcept_no") == "20250805000286"
