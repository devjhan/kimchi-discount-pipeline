"""application/screen.run_screen 단위 테스트.

cache hit / cache miss / dry-run / rule-pass / rule-fail / caution 경로 검증.
DART fetch 는 mock (dry_run=True 또는 api_key=None) 으로 회피. 정책/메커니즘
분리 후 run_screen 은 rule_for/profile_for closure 를 주입받는다 (stub 주입).
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from domains.screener.application.screen import run_screen, verdicts_as_json
from domains.screener.domain.ticker import FilingMetric
from domains.screener.io.financial_cache import CachePolicy, LiveFinancialCache
from domains.screener.io.universe_loader import UniverseEntry
from domains.screener.rules.factory import RuleFactory
from domains._shared.profile_registry.schema import (
    SCHEMA_VERSION,
    EnrichCutoffProfile,
    Provenance,
)
from domains._shared.time.clock import AsOfClock

KST = timezone(timedelta(hours=9))


class _FakeCitation:
    """CitationPort 테스트 stub — 주입 seam 검증용 (dry_run 경로에선 미호출)."""

    def format(self, source: str, ts: str, value: object) -> str:
        """G7 형식 흉내 — 실제 util 동치는 _shared 포트 테스트가 검증."""
        return f"{source}@{ts}={value}"


_CITATION = _FakeCitation()


@pytest.fixture(autouse=True)
def _freeze_kst_today(monkeypatch: pytest.MonkeyPatch) -> None:
    """LiveFinancialCache.get_snapshot 의 today 검증 우회."""
    from domains.screener import _boundary

    fixed = datetime(2026, 5, 15, 15, 30, tzinfo=KST)
    monkeypatch.setattr(_boundary, "now_kst", lambda: fixed)


@pytest.fixture
def policy() -> CachePolicy:
    return CachePolicy(
        financials_ttl_days=30,
        capital_signals_ttl_days=7,
        staleness_grace_days=14,
    )


def _seed_v4_cache(
    cache: LiveFinancialCache,
    *,
    ticker: str,
    op_income: float = 120.0,
    debt: float = 400.0,
    equity: float = 1000.0,
    finance_costs: float = 10.0,
    capex: float = 50.0,
    op_cf: float = 150.0,
    signals: list[dict] | None = None,
) -> None:
    filings = [
        FilingMetric(
            fiscal_period=f"{2022 + i}Y",
            period_end_date=date(2022 + i, 12, 31),
            filing_datetime=datetime(2023 + i, 3, 15, 18, 0, tzinfo=KST),
            kind="annual",
            is_amended=False,
            revenue=1000.0,
            operating_income=op_income,
            total_assets=2000.0,
            total_equity=equity,
            total_debt=debt,
            finance_costs=finance_costs,
            operating_cash_flow=op_cf,
            capex=capex,
            citation=f"DART@{2023+i}-03-15T18:00:00+09:00={{}}",
        )
        for i in range(3)
    ]
    cache.write_atomic(
        ticker,
        name="테스트",
        corp_code="00112378",
        bsns_year="2024",
        tax_rate=0.22,
        filings=filings,
        capital_signals_events=signals or [],
        metrics={"roic_annual": [0.07, 0.08, 0.09]},
        citations=["DART@..."],
    )


def _build_rule():
    """quality_floor profile + default strategy + hard_guards 로 Rule 트리 빌드."""
    profile = {
        "name": "quality_floor",
        "rule": {
            "type": "and",
            "name": "quality_floor",
            "children": [
                {
                    "type": "threshold",
                    "name": "ic_floor",
                    "metric_path": "latest_annual.interest_coverage",
                    "op": "ge",
                    "threshold": 4.0,
                },
                {
                    "type": "threshold",
                    "name": "de_ceiling",
                    "metric_path": "latest_annual.debt_to_equity",
                    "op": "le",
                    "threshold": 1.0,
                },
                {
                    "type": "signal_presence",
                    "name": "capital_allocation",
                    "required_any_of": ["dividend_payment"],
                },
            ],
        },
    }
    strategy = {
        "name": "default",
        "rule": {"type": "profile_ref", "profile": "quality_floor"},
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
    return RuleFactory.build_strategy(
        strategy, {"quality_floor": profile}, hard_guards, tax_rate=0.22
    )


def _enrichment_rule(threshold: float):
    """enrichments.nav_discount.discount_pct >= threshold + hard guards."""
    strat = {
        "name": "e",
        "rule": {
            "type": "threshold",
            "name": "nav_floor",
            "metric_path": "enrichments.nav_discount.discount_pct",
            "op": "ge",
            "threshold": threshold,
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
    return RuleFactory.build_strategy(strat, {}, hard_guards, tax_rate=0.22)


def _profile(required: tuple[str, ...]) -> EnrichCutoffProfile:
    return EnrichCutoffProfile(
        ticker="KR:000001",
        schema_version=SCHEMA_VERSION,
        profile_version=1,
        required_enrichments=required,
        cutoff_rules={"type": "and", "name": "c", "children": []},
        provenance=Provenance(
            committed_at="2026-06-01T16:00:00+09:00",
            committed_by="test",
            trigger="manual",
        ),
    )


def _fixed_rule_for(rule):
    return lambda ticker: rule


def _no_profile(ticker):
    return None


@pytest.mark.unit
def test_dry_run_yields_unknown_for_all(tmp_path: Path, policy: CachePolicy) -> None:
    """dry_run=True: cache miss 전부 verdict='unknown', fetched=0."""
    cache = LiveFinancialCache(base_dir=tmp_path / "cache", policy=policy)
    universe = (
        UniverseEntry(ticker="KR:A", name="A", source_citation=""),
        UniverseEntry(ticker="KR:B", name="B", source_citation=""),
    )
    clock = AsOfClock.at_market_close(date(2026, 5, 15))
    result = run_screen(
        rule_for=_fixed_rule_for(_build_rule()),
        profile_for=_no_profile,
        universe=universe,
        cache=cache,
        clock=clock,
        tax_rate=0.22,
        dart_api_key=None,
        corp_index={},
        citation=_CITATION,
        dry_run=True,
    )
    assert result.stats == {
        "total": 2,
        "pass": 0,
        "fail": 0,
        "caution": 0,
        "unknown": 2,
        "fetched": 0,
    }
    assert all(v.verdict == "unknown" for v in result.verdicts)


@pytest.mark.unit
def test_cache_hit_passes_rule(tmp_path: Path, policy: CachePolicy) -> None:
    """cache hit + rule 통과 → verdict='pass'."""
    cache = LiveFinancialCache(base_dir=tmp_path / "cache", policy=policy)
    _seed_v4_cache(
        cache,
        ticker="KR:A",
        signals=[
            {
                "event_datetime": "2025-08-05T23:59:59+09:00",
                "signal_type": "dividend_payment",
            }
        ],
    )
    universe = (UniverseEntry(ticker="KR:A", name="테스트", source_citation=""),)
    result = run_screen(
        rule_for=_fixed_rule_for(_build_rule()),
        profile_for=_no_profile,
        universe=universe,
        cache=cache,
        clock=AsOfClock.at_market_close(date(2026, 5, 15)),
        tax_rate=0.22,
        dart_api_key=None,
        corp_index={},
        citation=_CITATION,
        dry_run=True,
    )
    assert result.stats["pass"] == 1
    assert result.verdicts[0].verdict == "pass"


@pytest.mark.unit
def test_cache_hit_fails_when_hard_guard_violated(
    tmp_path: Path, policy: CachePolicy
) -> None:
    """interest_coverage < 1.5 → solvency_floor hard guard fail."""
    cache = LiveFinancialCache(base_dir=tmp_path / "cache", policy=policy)
    _seed_v4_cache(
        cache,
        ticker="KR:Z",
        op_income=1.0,
        finance_costs=10.0,  # IC = 0.1
    )
    universe = (UniverseEntry(ticker="KR:Z", name="Z", source_citation=""),)
    result = run_screen(
        rule_for=_fixed_rule_for(_build_rule()),
        profile_for=_no_profile,
        universe=universe,
        cache=cache,
        clock=AsOfClock.at_market_close(date(2026, 5, 15)),
        tax_rate=0.22,
        dart_api_key=None,
        corp_index={},
        citation=_CITATION,
        dry_run=True,
    )
    assert result.stats["fail"] == 1
    v = result.verdicts[0]
    assert v.verdict == "fail"
    assert any(reason.startswith("HARD_FLOOR:") for reason in v.reasons)


@pytest.mark.unit
def test_verdicts_as_json_includes_rule_tree(
    tmp_path: Path, policy: CachePolicy
) -> None:
    """verdicts_as_json 의 결과가 JSON-serializable + rule_tree 포함."""
    cache = LiveFinancialCache(base_dir=tmp_path / "cache", policy=policy)
    _seed_v4_cache(
        cache,
        ticker="KR:A",
        signals=[
            {
                "event_datetime": "2025-08-05T23:59:59+09:00",
                "signal_type": "dividend_payment",
            }
        ],
    )
    universe = (UniverseEntry(ticker="KR:A", name="테스트", source_citation=""),)
    result = run_screen(
        rule_for=_fixed_rule_for(_build_rule()),
        profile_for=_no_profile,
        universe=universe,
        cache=cache,
        clock=AsOfClock.at_market_close(date(2026, 5, 15)),
        tax_rate=0.22,
        dart_api_key=None,
        corp_index={},
        citation=_CITATION,
        dry_run=True,
    )
    blob = verdicts_as_json(result.verdicts)
    assert isinstance(blob, list)
    assert blob[0]["ticker"] == "KR:A"
    assert blob[0]["rule_tree"] is not None
    json.dumps(blob, ensure_ascii=False)  # serialize 가능


# ----------------------------------------------------------------------
# Step 4.2 — caution verdict + nested enrichment conditions
# ----------------------------------------------------------------------


@pytest.mark.unit
def test_missing_required_enrichment_yields_caution(
    tmp_path: Path, policy: CachePolicy
) -> None:
    """profile required=[nav_discount] + snapshot enrichments={} → caution (pass/fail 아님)."""
    cache = LiveFinancialCache(base_dir=tmp_path / "cache", policy=policy)
    _seed_v4_cache(cache, ticker="KR:A")
    universe = (UniverseEntry(ticker="KR:A", name="A", source_citation=""),)  # enrichments={}
    result = run_screen(
        rule_for=_fixed_rule_for(_build_rule()),
        profile_for=lambda t: _profile(("nav_discount",)),
        universe=universe,
        cache=cache,
        clock=AsOfClock.at_market_close(date(2026, 5, 15)),
        tax_rate=0.22,
        dart_api_key=None,
        corp_index={},
        citation=_CITATION,
        dry_run=True,
    )
    v = result.verdicts[0]
    assert v.verdict == "caution"
    assert any("missing_required_enrichment" in r for r in v.reasons)
    assert result.stats["caution"] == 1


@pytest.mark.unit
def test_caution_has_citations(tmp_path: Path, policy: CachePolicy) -> None:
    """caution verdict 은 unknown 과 달리 citations 보유 (면제 아님)."""
    cache = LiveFinancialCache(base_dir=tmp_path / "cache", policy=policy)
    _seed_v4_cache(cache, ticker="KR:A")
    universe = (UniverseEntry(ticker="KR:A", name="A", source_citation=""),)
    result = run_screen(
        rule_for=_fixed_rule_for(_build_rule()),
        profile_for=lambda t: _profile(("nav_discount",)),
        universe=universe,
        cache=cache,
        clock=AsOfClock.at_market_close(date(2026, 5, 15)),
        tax_rate=0.22,
        dart_api_key=None,
        corp_index={},
        citation=_CITATION,
        dry_run=True,
    )
    assert result.verdicts[0].citations  # 비어있지 않음


@pytest.mark.unit
def test_batch_continues_after_caution(tmp_path: Path, policy: CachePolicy) -> None:
    """3종목 중 1종목 결측 → 나머지 2종목 정상 평가 (배치 미중단)."""
    cache = LiveFinancialCache(base_dir=tmp_path / "cache", policy=policy)
    for t in ("KR:A", "KR:B", "KR:C"):
        _seed_v4_cache(
            cache,
            ticker=t,
            signals=[
                {
                    "event_datetime": "2025-08-05T23:59:59+09:00",
                    "signal_type": "dividend_payment",
                }
            ],
        )
    universe = (
        UniverseEntry(ticker="KR:A", name="A", source_citation=""),
        UniverseEntry(ticker="KR:B", name="B", source_citation=""),
        UniverseEntry(ticker="KR:C", name="C", source_citation=""),
    )
    # KR:A 만 nav_discount 필수 + enrichments 없음 → caution. B/C 는 프로파일 없음 → default.
    result = run_screen(
        rule_for=_fixed_rule_for(_build_rule()),
        profile_for=lambda t: _profile(("nav_discount",)) if t == "KR:A" else None,
        universe=universe,
        cache=cache,
        clock=AsOfClock.at_market_close(date(2026, 5, 15)),
        tax_rate=0.22,
        dart_api_key=None,
        corp_index={},
        citation=_CITATION,
        dry_run=True,
    )
    assert result.stats["total"] == 3
    assert result.stats["caution"] == 1
    by_ticker = {v.ticker: v for v in result.verdicts}
    assert by_ticker["KR:A"].verdict == "caution"
    assert by_ticker["KR:B"].verdict in ("pass", "fail")
    assert by_ticker["KR:C"].verdict in ("pass", "fail")


@pytest.mark.unit
def test_nested_condition_pass(tmp_path: Path, policy: CachePolicy) -> None:
    """enrichments={nav_discount:{discount_pct:0.25}} + cutoff >=0.20 → pass."""
    cache = LiveFinancialCache(base_dir=tmp_path / "cache", policy=policy)
    _seed_v4_cache(cache, ticker="KR:A")
    universe = (
        UniverseEntry(
            ticker="KR:A",
            name="A",
            source_citation="",
            enrichments={"nav_discount": {"discount_pct": 0.25}},
        ),
    )
    result = run_screen(
        rule_for=_fixed_rule_for(_enrichment_rule(0.20)),
        profile_for=_no_profile,
        universe=universe,
        cache=cache,
        clock=AsOfClock.at_market_close(date(2026, 5, 15)),
        tax_rate=0.22,
        dart_api_key=None,
        corp_index={},
        citation=_CITATION,
        dry_run=True,
    )
    assert result.verdicts[0].verdict == "pass"


@pytest.mark.unit
def test_nested_condition_fail(tmp_path: Path, policy: CachePolicy) -> None:
    """discount 0.10 + cutoff >=0.20 → fail (caution 아님 — 데이터 존재, 룰 미달)."""
    cache = LiveFinancialCache(base_dir=tmp_path / "cache", policy=policy)
    _seed_v4_cache(cache, ticker="KR:A")
    universe = (
        UniverseEntry(
            ticker="KR:A",
            name="A",
            source_citation="",
            enrichments={"nav_discount": {"discount_pct": 0.10}},
        ),
    )
    result = run_screen(
        rule_for=_fixed_rule_for(_enrichment_rule(0.20)),
        profile_for=_no_profile,
        universe=universe,
        cache=cache,
        clock=AsOfClock.at_market_close(date(2026, 5, 15)),
        tax_rate=0.22,
        dart_api_key=None,
        corp_index={},
        citation=_CITATION,
        dry_run=True,
    )
    assert result.verdicts[0].verdict == "fail"


@pytest.mark.unit
def test_screener_parity_empty_registry(tmp_path: Path, policy: CachePolicy) -> None:
    """빈 registry (profile_for=None 전 종목) → default_rule → caution 0 (회귀)."""
    cache = LiveFinancialCache(base_dir=tmp_path / "cache", policy=policy)
    _seed_v4_cache(
        cache,
        ticker="KR:A",
        signals=[
            {
                "event_datetime": "2025-08-05T23:59:59+09:00",
                "signal_type": "dividend_payment",
            }
        ],
    )
    _seed_v4_cache(cache, ticker="KR:Z", op_income=1.0, finance_costs=10.0)  # IC=0.1 → fail
    universe = (
        UniverseEntry(ticker="KR:A", name="A", source_citation=""),
        UniverseEntry(ticker="KR:Z", name="Z", source_citation=""),
    )
    rule = _build_rule()
    result = run_screen(
        rule_for=_fixed_rule_for(rule),
        profile_for=_no_profile,
        universe=universe,
        cache=cache,
        clock=AsOfClock.at_market_close(date(2026, 5, 15)),
        tax_rate=0.22,
        dart_api_key=None,
        corp_index={},
        citation=_CITATION,
        dry_run=True,
    )
    by_ticker = {v.verdict for v in result.verdicts}
    assert result.stats["caution"] == 0
    assert result.stats["unknown"] == 0
    assert by_ticker == {"pass", "fail"}
