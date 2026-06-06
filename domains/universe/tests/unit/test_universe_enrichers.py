"""universe.enrichers — Enricher ABC + registry + factory + 2 enricher 검증.

Run 5 scope:
- ``NavDiscountEnricher`` — KIS_APP_KEY 부재 / subsidiaries_map 부재 시 skip,
  정상 시 attributes 계산
- ``SpreadZScoreEnricher`` — common/preferred metadata 부재 시 skip,
  KIS 시리즈 mock 으로 z-score 계산
- ``factory.build_enricher`` — type dispatch + 누락 type / name / 미등록 type 거부
- ``registry`` — 중복 등록 차단
- ``EnrichedEntry`` — from_base + with_enrichment immutable wrapping
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from domains._shared.time.clock import AsOfClock
from domains.universe import _boundary
from domains.universe.domain.enriched import EnrichedEntry, EnrichmentResult
from domains.universe.domain.entry import UniverseEntry
from domains.universe.enrichers.base import EnrichContext, Enricher
from domains.universe.enrichers.factory import build_enrichers, build_enricher
from domains.universe.enrichers.nav_discount import NavDiscountEnricher
from domains.universe.enrichers.registry import ENRICHER_TYPES, register_enricher
from domains.universe.enrichers.spread_zscore import SpreadZScoreEnricher


@pytest.fixture(autouse=True)
def _isolate_nav_history(tmp_path, monkeypatch: pytest.MonkeyPatch):
    """nav_discount enricher 가 nav-history 를 append (B-2) → 실제 telemetry/ 오염 방지.

    NAV_HISTORY_DIR 을 per-test tmp 로 격리 (utils.nav_history_dir env 우선).
    """
    monkeypatch.setenv("NAV_HISTORY_DIR", str(tmp_path / "_navhist"))
    yield


def _ctx(env: dict[str, str] | None = None, allow_yahoo: bool = False) -> EnrichContext:
    return EnrichContext(
        clock=AsOfClock.at_market_close(date(2026, 5, 17)),
        env=env if env is not None else {"DART_API_KEY": "dummy", "KIS_APP_KEY": "dummy", "KIS_APP_SECRET": "dummy"},
        allow_yahoo=allow_yahoo,
    )


def _entry(
    ticker: str = "KR:003550",
    source_category: str = "holding_company",
    metadata: dict[str, Any] | None = None,
) -> UniverseEntry:
    return UniverseEntry(
        ticker=ticker,
        name=ticker,
        source_category=source_category,
        inclusion_reason="r",
        fetched_at="t",
        source_citation="c",
        metadata=metadata or {},
    )


# ----------------------------------------------------------------------
# EnrichedEntry
# ----------------------------------------------------------------------


@pytest.mark.unit
def test_enriched_from_base_preserves_fields() -> None:
    base = _entry()
    enriched = EnrichedEntry.from_base(base)
    assert enriched.ticker == base.ticker
    assert enriched.source_category == base.source_category
    assert enriched.metadata == base.metadata
    assert enriched.enrichments == {}
    assert enriched.enrichment_citations == ()


@pytest.mark.unit
def test_enriched_with_enrichment_attaches_and_immutable() -> None:
    base = _entry()
    enriched = EnrichedEntry.from_base(base)
    result = EnrichmentResult(
        attributes={"discount_pct": 0.65, "nav_estimate": 100.0},
        citations=("KIS@t=001",),
        warnings=("w1",),
    )
    new = enriched.with_enrichment("nav_discount", result)
    # original 불변
    assert enriched.enrichments == {}
    # new 에 attach
    assert new.enrichments == {"nav_discount": {"discount_pct": 0.65, "nav_estimate": 100.0}}
    assert new.enrichment_citations == ("KIS@t=001",)
    assert new.enrichment_warnings == ("w1",)
    assert new.enrichment_skips == {}


@pytest.mark.unit
def test_enriched_with_enrichment_skip_records_reason() -> None:
    base = _entry()
    enriched = EnrichedEntry.from_base(base)
    result = EnrichmentResult(
        attributes={},
        skip_reason="API key missing",
    )
    new = enriched.with_enrichment("nav_discount", result)
    assert new.enrichments == {}  # attributes not attached
    assert new.enrichment_skips == {"nav_discount": "API key missing"}


@pytest.mark.unit
def test_enriched_citations_dedup_across_enrichers() -> None:
    base = _entry()
    enriched = EnrichedEntry.from_base(base)
    r1 = EnrichmentResult(attributes={"a": 1}, citations=("c1", "c2"))
    r2 = EnrichmentResult(attributes={"b": 2}, citations=("c2", "c3"))
    new = enriched.with_enrichment("e1", r1).with_enrichment("e2", r2)
    # c2 dedup
    assert new.enrichment_citations == ("c1", "c2", "c3")


# ----------------------------------------------------------------------
# NavDiscountEnricher
# ----------------------------------------------------------------------


@pytest.mark.unit
def test_nav_discount_skip_when_no_kis_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    src = NavDiscountEnricher(
        name="nav",
        subsidiaries_map={"KR:003550": [{"stock_code": "051910", "ownership_pct": 0.3, "listed": True}]},
    )
    result = src.enrich(_entry(), _ctx(env={}))  # no KIS keys
    assert result.skip_reason is not None
    assert "KIS_APP_KEY" in result.skip_reason
    assert result.attributes == {}


@pytest.mark.unit
def test_nav_discount_skip_when_ticker_not_in_map() -> None:
    src = NavDiscountEnricher(
        name="nav",
        subsidiaries_map={"KR:999999": [{"stock_code": "051910"}]},
    )
    result = src.enrich(_entry(ticker="KR:003550"), _ctx())
    assert result.skip_reason is not None
    assert "KR:003550" in result.skip_reason


@pytest.mark.unit
def test_nav_discount_computes_attributes_with_mock_kis(monkeypatch: pytest.MonkeyPatch) -> None:
    """KIS fetch mock 으로 parent + sub 시총 → nav / discount 계산 검증."""

    def _fake_token(env, cache_path=None):  # type: ignore[no-untyped-def]
        return "TOK"

    def _fake_price(*, token, app_key, app_secret, stock_code):  # type: ignore[no-untyped-def]
        # parent (003550): 100억, sub (051910): 200억
        mcap_map = {"003550": (1_000_000, 10000), "051910": (2_000_000, 10000)}
        lstn, prpr = mcap_map.get(stock_code, (0, 0))
        return {"lstn_stcn": str(lstn), "stck_prpr": str(prpr)}

    monkeypatch.setattr(_boundary, "kis_issue_access_token", _fake_token)
    monkeypatch.setattr(_boundary, "kis_fetch_current_price", _fake_price)

    src = NavDiscountEnricher(
        name="nav",
        subsidiaries_map={
            "KR:003550": [
                {"stock_code": "051910", "name": "LG화학", "ownership_pct": 0.30, "listed": True},
            ],
        },
    )
    result = src.enrich(_entry(ticker="KR:003550"), _ctx())
    assert result.skip_reason is None
    a = result.attributes
    # parent_mcap = 1_000_000 * 10000 = 10_000_000_000
    assert a["parent_market_cap"] == 10_000_000_000
    # nav = 2_000_000 * 10000 * 0.30 = 6_000_000_000
    assert a["nav_estimate"] == 6_000_000_000
    # discount = 1 - parent/nav = 1 - (10e9 / 6e9) ≈ -0.6667 (parent > nav)
    assert a["discount_pct"] == round(1.0 - 10_000_000_000 / 6_000_000_000, 4)
    assert len(a["subsidiaries"]) == 1
    # citations: parent + sub
    assert len(result.citations) == 2


@pytest.mark.unit
def test_nav_discount_skips_indirect_subsidiaries(monkeypatch: pytest.MonkeyPatch) -> None:
    """indirect_via 가 set 된 자회사는 NAV 합산 제외."""

    def _fake_token(env, cache_path=None):  # type: ignore[no-untyped-def]
        return "TOK"

    def _fake_price(*, token, app_key, app_secret, stock_code):  # type: ignore[no-untyped-def]
        return {"lstn_stcn": "1000", "stck_prpr": "1000"}

    monkeypatch.setattr(_boundary, "kis_issue_access_token", _fake_token)
    monkeypatch.setattr(_boundary, "kis_fetch_current_price", _fake_price)

    src = NavDiscountEnricher(
        name="nav",
        subsidiaries_map={
            "KR:003550": [
                {"stock_code": "051910", "ownership_pct": 0.30, "listed": True},
                {"stock_code": "373220", "ownership_pct": 0.0, "listed": True, "indirect_via": "051910"},
            ],
        },
    )
    result = src.enrich(_entry(ticker="KR:003550"), _ctx())
    assert result.skip_reason is None
    # 자회사 2 entry 보존하지만 indirect 는 contribution=None
    subs = result.attributes["subsidiaries"]
    assert len(subs) == 2
    indirect = next(s for s in subs if s["stock_code"] == "373220")
    assert indirect["contribution"] is None
    assert "indirect" in indirect["skip_reason"]


@pytest.mark.unit
def test_nav_discount_appends_nav_history_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    """enrich() 가 nav-history store 에 오늘 snapshot 1건 append (B-2 writer) + 멱등."""
    from domains._shared import nav_history

    monkeypatch.setattr(_boundary, "kis_issue_access_token", lambda env, cache_path=None: "TOK")

    def _fake_price(*, token, app_key, app_secret, stock_code):  # type: ignore[no-untyped-def]
        mcap_map = {"003550": (1_000_000, 10000), "051910": (2_000_000, 10000)}
        lstn, prpr = mcap_map.get(stock_code, (0, 0))
        return {"lstn_stcn": str(lstn), "stck_prpr": str(prpr)}

    monkeypatch.setattr(_boundary, "kis_fetch_current_price", _fake_price)
    src = NavDiscountEnricher(
        name="nav",
        subsidiaries_map={
            "KR:003550": [{"stock_code": "051910", "ownership_pct": 0.30, "listed": True}]
        },
    )
    src.enrich(_entry(ticker="KR:003550"), _ctx())
    hist = nav_history.load_nav_history("KR:003550")
    assert len(hist) == 1
    assert hist[0]["date"] == "2026-05-17"  # ctx.clock.trading_date (wall-clock 아님)
    # premium = parent_mcap/nav - 1 = 10e9/6e9 - 1 (parent > nav → premium 양수)
    assert hist[0]["premium_pct"] == round(10_000_000_000 / 6_000_000_000 - 1.0, 4)
    # 같은 거래일 재실행 → 멱등 (중복 append 안 함)
    src.enrich(_entry(ticker="KR:003550"), _ctx())
    assert len(nav_history.load_nav_history("KR:003550")) == 1


# ----------------------------------------------------------------------
# SpreadZScoreEnricher
# ----------------------------------------------------------------------


@pytest.mark.unit
def test_spread_zscore_skip_when_missing_metadata() -> None:
    src = SpreadZScoreEnricher(name="z")
    result = src.enrich(_entry(metadata={}), _ctx())
    assert result.skip_reason is not None
    assert "common / preferred" in result.skip_reason


@pytest.mark.unit
def test_spread_zscore_skip_when_kis_unavailable_and_no_yahoo(monkeypatch: pytest.MonkeyPatch) -> None:
    src = SpreadZScoreEnricher(name="z", lookback_days=100, min_observations=30)
    result = src.enrich(
        _entry(
            source_category="preferred_share_pair",
            metadata={"common": "005930", "preferred": "005935", "market": "KOSPI"},
        ),
        _ctx(env={}),  # no KIS keys
    )
    assert result.skip_reason is not None
    assert "fetch 실패" in result.skip_reason
    assert result.attributes["price_source"] == "unavailable"


@pytest.mark.unit
def test_spread_zscore_with_mock_kis_series(monkeypatch: pytest.MonkeyPatch) -> None:
    """KIS 일봉 mock → spread + z-score 계산."""

    def _fake_token(env, cache_path=None):  # type: ignore[no-untyped-def]
        return "TOK"

    # 100 영업일 mock series — common: 일정 100, preferred: 80 → spread=0.2 constant → std=0 → z=None
    def _fake_ohlcv(*, token, app_key, app_secret, stock_code, period_days, end_date, adjusted=True):  # type: ignore[no-untyped-def]
        # date 가 cursor_end 부터 100일 거꾸로
        from datetime import datetime, timedelta

        anchor = datetime.strptime(end_date or "20260517", "%Y%m%d")
        rows = []
        price = 100 if stock_code == "005930" else 80
        for i in range(period_days):
            d = anchor - timedelta(days=i)
            rows.append({"stck_bsop_date": d.strftime("%Y%m%d"), "stck_clpr": str(price)})
        return rows

    monkeypatch.setattr(_boundary, "kis_issue_access_token", _fake_token)
    monkeypatch.setattr(_boundary, "kis_fetch_daily_ohlcv", _fake_ohlcv)

    # min_observations=10 으로 낮춰 빠른 검증
    src = SpreadZScoreEnricher(name="z", lookback_days=50, min_observations=10, z_min=1.0)
    result = src.enrich(
        _entry(
            source_category="preferred_share_pair",
            metadata={"common": "005930", "preferred": "005935", "market": "KOSPI"},
        ),
        _ctx(),
    )
    assert result.skip_reason is None
    a = result.attributes
    assert a["common_close"] == 100.0
    assert a["preferred_close"] == 80.0
    assert a["current_spread_pct"] == 0.2
    # constant spread → std=0 → z=None → catalyst_flag=False
    assert a["std_spread_pct"] == 0
    assert a["z_score"] is None
    assert a["catalyst_flag"] is False
    assert a["price_source"] == "KIS"


# ----------------------------------------------------------------------
# Factory + Registry
# ----------------------------------------------------------------------


@pytest.mark.unit
def test_factory_builds_nav_discount() -> None:
    spec = {
        "type": "nav_discount",
        "name": "nav",
        "subsidiaries_map": {"KR:003550": [{"stock_code": "051910"}]},
    }
    e = build_enricher(spec)
    assert isinstance(e, NavDiscountEnricher)


@pytest.mark.unit
def test_factory_builds_spread_zscore() -> None:
    spec = {
        "type": "spread_zscore",
        "name": "z",
        "lookback_days": 500,
    }
    e = build_enricher(spec)
    assert isinstance(e, SpreadZScoreEnricher)
    assert e.lookback_days == 500


@pytest.mark.unit
def test_factory_rejects_unknown_type() -> None:
    with pytest.raises(ValueError, match="unknown enricher type"):
        build_enricher({"type": "nonexistent", "name": "x"})


@pytest.mark.unit
def test_factory_rejects_missing_fields() -> None:
    with pytest.raises(ValueError, match="missing 'type'"):
        build_enricher({"name": "x"})
    with pytest.raises(ValueError, match="missing 'name'"):
        build_enricher({"type": "nav_discount"})


@pytest.mark.unit
def test_nav_discount_from_spec_missing_map_rejected() -> None:
    with pytest.raises(ValueError, match="subsidiaries_map"):
        NavDiscountEnricher.from_spec({"type": "nav_discount", "name": "x"})


@pytest.mark.unit
def test_registry_rejects_duplicate_registration() -> None:
    with pytest.raises(ValueError, match="already registered"):

        @register_enricher("nav_discount")  # 이미 등록됨
        class Dupe(Enricher):  # type: ignore[misc]
            name: str = "x"
            applies_to: frozenset[str] = frozenset()

            @classmethod
            def from_spec(cls, spec):  # type: ignore[no-untyped-def]
                return cls()

            def enrich(self, entry, ctx):  # type: ignore[no-untyped-def]
                return EnrichmentResult(attributes={})


@pytest.mark.unit
def test_enrichers_yaml_loadable_and_dispatches() -> None:
    """config/enrichers.yaml 이 build_enrichers() 로 인스턴스화 가능."""
    cfg = _boundary.load_enrichers_config()
    assert cfg["schema"] == "universe-enrichers-v1"
    enrichers = build_enrichers(cfg["enrichers"])
    types = {type(e).__name__ for e in enrichers}
    assert "NavDiscountEnricher" in types
    assert "SpreadZScoreEnricher" in types


@pytest.mark.unit
def test_registered_enricher_types_includes_run5_set() -> None:
    assert "nav_discount" in ENRICHER_TYPES
    assert "spread_zscore" in ENRICHER_TYPES
