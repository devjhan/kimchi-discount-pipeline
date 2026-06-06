"""Phase 3 회귀 — build_universe 의 POLICY MODE(required_enrichments_for) 가
backward-compat applies_to 모드와 byte-identical 산출을 내는지 검증.

결정론 stub (네트워크 0) 로 selection 만 변수화. synthetic registry 는
applies_to 를 정확히 재현 (ticker -> {enricher_name | source_category in applies_to}).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date

import pytest

from domains._shared.time.clock import AsOfClock
from domains.universe.application.build_universe import build_universe
from domains.universe.domain.enriched import EnrichmentResult
from domains.universe.domain.entry import UniverseEntry
from domains.universe.enrichers.base import EnrichContext, Enricher
from domains.universe.sources.base import (
    DiscoveryContext,
    DiscoverySource,
    SourceResult,
)


@dataclass(frozen=True)
class _StubSource(DiscoverySource):
    name: str
    source_category: str
    _entries: tuple[UniverseEntry, ...]

    @classmethod
    def from_spec(cls, spec):  # type: ignore[no-untyped-def]
        raise NotImplementedError("test fixture only")

    def discover(self, ctx: DiscoveryContext) -> SourceResult:
        return SourceResult(entries=self._entries, warnings=(), degraded=False)


@dataclass(frozen=True)
class _StubEnricher(Enricher):
    """결정론 enricher — 고정 EnrichmentResult 반환 (네트워크 0)."""

    name: str
    applies_to: frozenset[str]

    @classmethod
    def from_spec(cls, spec):  # type: ignore[no-untyped-def]
        raise NotImplementedError("test fixture only")

    def enrich(self, entry: UniverseEntry, ctx: EnrichContext) -> EnrichmentResult:
        return EnrichmentResult(
            attributes={"stub_value": 1.0, "from": self.name},
            citations=(f"STUB@2026-05-17T00:00:00+09:00={self.name}",),
            warnings=(f"{self.name}:{entry.ticker} stub-warn",),
        )


def _entry(ticker: str, category: str) -> UniverseEntry:
    return UniverseEntry(
        ticker=ticker,
        name=ticker,
        source_category=category,
        inclusion_reason="r",
        fetched_at="t",
        source_citation=f"SRC@2026-05-17T00:00:00+09:00={ticker}",
    )


def _clock() -> AsOfClock:
    return AsOfClock.at_market_close(date(2026, 5, 17))


def _stub_sources_and_enrichers():
    # 각 ticker 는 단일 source_category 에만 등장 (실제 config 와 동형 — 카테고리 disjoint).
    sources = (
        _StubSource(
            "hold",
            "holding_company",
            (_entry("KR:001", "holding_company"), _entry("KR:002", "holding_company")),
        ),
        _StubSource("pref", "preferred_share_pair", (_entry("KR:003", "preferred_share_pair"),)),
        _StubSource("other", "manual_addition", (_entry("KR:004", "manual_addition"),)),
    )
    enrichers = (
        _StubEnricher("nav_discount", frozenset({"holding_company"})),
        _StubEnricher("spread_zscore", frozenset({"preferred_share_pair"})),
    )
    return sources, enrichers


def _registry_reproducing_applies_to(enrichers, entries):
    """applies_to 정확 재현: ticker -> {enricher.name | entry.source_category in applies_to}."""
    mapping: dict[str, frozenset[str]] = {}
    for e in entries:
        mapping[e.ticker] = frozenset(
            en.name for en in enrichers if e.source_category in en.applies_to
        )
    return lambda ticker: mapping.get(ticker, frozenset())


@pytest.mark.unit
def test_registry_mode_matches_applies_to_mode() -> None:
    sources, enrichers = _stub_sources_and_enrichers()
    old = build_universe(
        sources=sources, enrichers=enrichers, clock=_clock(), env={}, dry_run=False
    )
    reg_fn = _registry_reproducing_applies_to(enrichers, old.entries)
    new = build_universe(
        sources=sources,
        enrichers=enrichers,
        clock=_clock(),
        env={},
        dry_run=False,
        required_enrichments_for=reg_fn,
    )
    assert [asdict(e) for e in old.entries] == [asdict(e) for e in new.entries]
    assert old.stats == new.stats
    assert old.warnings == new.warnings
    # sanity: 보강이 실제로 일어났는지 (parity 가 trivially-empty 가 아님 확인)
    assert old.stats.get("enriched_by") == {"nav_discount": 2, "spread_zscore": 1}


@pytest.mark.unit
def test_empty_registry_skips_all_enrichment() -> None:
    """POLICY MODE + 빈 registry (전 종목 frozenset()) → 보강 0 (cutover 의미 확인)."""
    sources, enrichers = _stub_sources_and_enrichers()
    result = build_universe(
        sources=sources,
        enrichers=enrichers,
        clock=_clock(),
        env={},
        dry_run=False,
        required_enrichments_for=lambda ticker: frozenset(),
    )
    assert "enriched_by" not in result.stats  # 아무 enricher 도 실행 안 됨
    assert all(e.enrichments == {} for e in result.entries)


@pytest.mark.unit
def test_policy_mode_can_target_specific_ticker() -> None:
    """POLICY MODE 는 source_category 무관 — ticker 단위 선택 (정책/메커니즘 분리 핵심)."""
    sources, enrichers = _stub_sources_and_enrichers()
    # KR:004 (manual_addition) 는 applies_to 모드에선 미보강이지만, policy 가 명시하면 보강.
    reg = {"KR:004": frozenset({"nav_discount"})}
    result = build_universe(
        sources=sources,
        enrichers=enrichers,
        clock=_clock(),
        env={},
        dry_run=False,
        required_enrichments_for=lambda t: reg.get(t, frozenset()),
    )
    by_ticker = {e.ticker: e for e in result.entries}
    assert "nav_discount" in by_ticker["KR:004"].enrichments
    assert by_ticker["KR:001"].enrichments == {}  # 정책 미지정 → 미보강
