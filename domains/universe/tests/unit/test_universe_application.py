"""build_universe orchestrator (Run 4) — fan-in / dedup / exclusions / stats 검증."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pytest

from domains._shared.time.clock import AsOfClock
from domains.universe.application.build_universe import build_universe
from domains.universe.domain.entry import UniverseEntry
from domains.universe.sources.base import DiscoveryContext, DiscoverySource, SourceResult


@dataclass(frozen=True)
class _StubSource(DiscoverySource):
    """test fixture — discover() 가 미리 주입된 SourceResult 반환."""

    name: str
    source_category: str
    _entries: tuple[UniverseEntry, ...]
    _warnings: tuple[str, ...] = ()
    _degraded: bool = False

    @classmethod
    def from_spec(cls, spec):  # type: ignore[no-untyped-def]
        raise NotImplementedError("test fixture only")

    def discover(self, ctx: DiscoveryContext) -> SourceResult:
        return SourceResult(
            entries=self._entries,
            warnings=self._warnings,
            degraded=self._degraded,
        )


def _entry(ticker: str, source_category: str, citation: str = "c1") -> UniverseEntry:
    return UniverseEntry(
        ticker=ticker,
        name=ticker,
        source_category=source_category,
        inclusion_reason="r",
        fetched_at="t",
        source_citation=citation,
    )


def _clock() -> AsOfClock:
    return AsOfClock.at_market_close(date(2026, 5, 17))


# ----------------------------------------------------------------------
# Fan-in
# ----------------------------------------------------------------------


@pytest.mark.unit
def test_build_universe_aggregates_entries_from_all_sources() -> None:
    sources = (
        _StubSource("a", "manual_addition", (_entry("KR:001", "manual_addition"),)),
        _StubSource("b", "treasury_action", (_entry("KR:002", "treasury_action"),)),
    )
    result = build_universe(
        sources=sources, exclusions=frozenset(), clock=_clock(), env={}
    )
    assert len(result.entries) == 2
    assert {e.ticker for e in result.entries} == {"KR:001", "KR:002"}
    assert result.stats["total"] == 2
    assert result.stats["by_source_category"] == {
        "manual_addition": 1,
        "treasury_action": 1,
    }
    assert result.stats["excluded"] == 0
    assert result.stats["dry_run"] is False


@pytest.mark.unit
def test_build_universe_aggregates_warnings_and_skipped() -> None:
    sources = (
        _StubSource("a", "x", (), ("a: no api key",)),  # 0 entries + warning → skipped
        _StubSource("b", "y", (_entry("KR:003", "y"),), ("b: minor",)),  # 1 entry + warning → not skipped
    )
    result = build_universe(
        sources=sources, exclusions=frozenset(), clock=_clock(), env={}
    )
    assert len(result.entries) == 1
    assert len(result.warnings) == 2
    assert len(result.skipped_sources) == 1
    assert result.skipped_sources[0].source == "a"
    assert "no api key" in result.skipped_sources[0].reason


@pytest.mark.unit
def test_build_universe_dedup_same_key_preserves_different_category() -> None:
    """같은 ticker 가 (a) 다른 source_category 이거나 (b) 같은 category + 다른 citation 이면 보존."""
    sources = (
        _StubSource(
            "a",
            "treasury_action",
            (
                _entry("KR:001", "treasury_action", citation="c1"),
                _entry("KR:001", "treasury_action", citation="c1"),  # exact dup → drop
                _entry("KR:001", "treasury_action", citation="c2"),  # diff citation → keep
                _entry("KR:001", "activist_filing", citation="c3"),  # diff category → keep
            ),
        ),
    )
    result = build_universe(
        sources=sources, exclusions=frozenset(), clock=_clock(), env={}
    )
    assert len(result.entries) == 3
    assert result.stats["by_source_category"] == {
        "treasury_action": 2,
        "activist_filing": 1,
    }


# ----------------------------------------------------------------------
# Exclusions
# ----------------------------------------------------------------------


@pytest.mark.unit
def test_build_universe_exclusions_filter_by_ticker() -> None:
    sources = (
        _StubSource(
            "a", "x",
            (
                _entry("KR:001", "x"),
                _entry("KR:002", "x"),
                _entry("KR:003", "x"),
            ),
        ),
    )
    result = build_universe(
        sources=sources,
        exclusions=frozenset({"KR:002"}),
        clock=_clock(),
        env={},
    )
    assert {e.ticker for e in result.entries} == {"KR:001", "KR:003"}
    assert result.stats["excluded"] == 1


@pytest.mark.unit
def test_build_universe_exclusions_apply_across_source_categories() -> None:
    """exclusions 는 ticker 기준 — 같은 ticker 가 여러 category 에 있어도 모두 제외."""
    sources = (
        _StubSource("a", "treasury_action", (_entry("KR:001", "treasury_action"),)),
        _StubSource("b", "activist_filing", (_entry("KR:001", "activist_filing"),)),
    )
    result = build_universe(
        sources=sources,
        exclusions=frozenset({"KR:001"}),
        clock=_clock(),
        env={},
    )
    assert result.entries == ()
    assert result.stats["excluded"] == 2


# ----------------------------------------------------------------------
# Degraded sources
# ----------------------------------------------------------------------


@pytest.mark.unit
def test_build_universe_records_degraded_source_names() -> None:
    sources = (
        _StubSource("a", "x", (_entry("KR:001", "x"),), _degraded=True),
        _StubSource("b", "y", (_entry("KR:002", "y"),)),
    )
    result = build_universe(
        sources=sources, exclusions=frozenset(), clock=_clock(), env={}
    )
    assert result.stats.get("degraded_sources") == ["a"]


@pytest.mark.unit
def test_build_universe_no_degraded_sources_omits_key() -> None:
    sources = (_StubSource("a", "x", (_entry("KR:001", "x"),)),)
    result = build_universe(
        sources=sources, exclusions=frozenset(), clock=_clock(), env={}
    )
    assert "degraded_sources" not in result.stats


# ----------------------------------------------------------------------
# Dry-run
# ----------------------------------------------------------------------


@pytest.mark.unit
def test_build_universe_dry_run_skips_all_sources() -> None:
    """dry-run 은 모든 source.discover() 를 호출하지 않음."""

    @dataclass(frozen=True)
    class _ExplodingSource(DiscoverySource):
        name: str = "boom"
        source_category: str = "x"

        @classmethod
        def from_spec(cls, spec):  # type: ignore[no-untyped-def]
            raise NotImplementedError

        def discover(self, ctx):
            raise AssertionError("dry-run 인데 호출됨")

    result = build_universe(
        sources=(_ExplodingSource(),),
        exclusions=frozenset(),
        clock=_clock(),
        env={},
        dry_run=True,
    )
    assert result.entries == ()
    assert result.stats["dry_run"] is True
    assert any("dry-run" in w for w in result.warnings)


# ----------------------------------------------------------------------
# Empty
# ----------------------------------------------------------------------


@pytest.mark.unit
def test_build_universe_empty_sources_produces_empty_envelope() -> None:
    """G11 default-no-action — sources 0개도 envelope 가 valid."""
    result = build_universe(
        sources=(), exclusions=frozenset(), clock=_clock(), env={}
    )
    assert result.entries == ()
    assert result.warnings == ()
    assert result.skipped_sources == ()
    assert result.stats == {
        "total": 0,
        "by_source_category": {},
        "excluded": 0,
        "dry_run": False,
    }
