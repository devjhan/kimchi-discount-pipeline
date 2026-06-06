"""build_universe — Stage 1 fan-in orchestrator + enrichment phase.

N 개 DiscoverySource 를 순차 호출 → entries union → dedup → exclusions 적용 →
Enricher 들이 applies_to 매칭 source_category 의 entry 에 attribute attach →
UniverseResult 반환.

screener 의 ``application/screen.py`` 와 동등한 layer. 차이:
- screener: 1 ticker × N rule 의 cartesian eval (predicate evaluator)
- universe: N source → union → enrichment (fan-in collector + vector mapper)

I/O 책임 없음 — file write / stdout 는 main.py 책임. 본 함수는 pure
(except DiscoverySource / Enricher 들이 자체 IO 수행).
"""
from __future__ import annotations

from typing import Callable, Mapping

from domains._shared.time.clock import AsOfClock
from domains.universe.domain.enriched import EnrichedEntry
from domains.universe.domain.entry import UniverseEntry
from domains.universe.domain.result import SkippedSource, UniverseResult
from domains.universe.enrichers.base import EnrichContext, Enricher
from domains.universe.sources.base import DiscoveryContext, DiscoverySource


def build_universe(
    *,
    sources: tuple[DiscoverySource, ...],
    enrichers: tuple[Enricher, ...] = (),
    exclusions: frozenset[str] = frozenset(),
    clock: AsOfClock,
    env: Mapping[str, str],
    allow_yahoo: bool = False,
    dry_run: bool = False,
    required_enrichments_for: Callable[[str], frozenset[str]] | None = None,
) -> UniverseResult:
    """fan-in discovery → dedup → exclusions → enrichment → stats.

    ``dry_run=True`` 면 source.discover() 와 enricher.enrich() 모두 skip — 빈
    universe 산출. legacy 의 "manual_additions 만 적용" 모드는 더 이상 없음 (sources
    전부 균등하게 skip).

    ``required_enrichments_for`` (DI seam):
    - ``None`` (기본) → BACKWARD-COMPAT: 기존 ``applies_to`` 정적 필터 (회귀 기준선).
    - ``ticker -> frozenset[str]`` → POLICY MODE: 종목별 ``required_enrichments``
      (profile_registry 가 결정). 선언된 enricher 만 실행 (불필요 fetch 제거).
    registry I/O 는 main.py 의 closure 책임 — 본 함수는 순수 유지.
    """
    ctx = DiscoveryContext(clock=clock, env=env)

    all_entries: list[UniverseEntry] = []
    all_warnings: list[str] = []
    skipped: list[SkippedSource] = []
    degraded_sources: list[str] = []

    if dry_run:
        all_warnings.append(
            "--dry-run: source discovery + enrichment skipped"
        )
    else:
        for src in sources:
            result = src.discover(ctx)
            all_entries.extend(result.entries)
            all_warnings.extend(result.warnings)
            if result.degraded:
                degraded_sources.append(src.name)
            if not result.entries and result.warnings:
                skipped.append(
                    SkippedSource(source=src.name, reason=result.warnings[0])
                )

    # dedup: same (ticker, source_category, source_citation) — 다른 source_category 보존
    merged = _dedup(all_entries)

    # exclusions: ticker 기준 set membership
    kept_base = [e for e in merged if e.ticker not in exclusions]
    excluded_count = len(merged) - len(kept_base)

    # enrichment phase
    enrich_ctx = EnrichContext(clock=clock, env=env, allow_yahoo=allow_yahoo)
    enriched_by: dict[str, int] = {}
    enriched_entries: list[EnrichedEntry] = []
    for base in kept_base:
        entry = EnrichedEntry.from_base(base)
        if not dry_run:
            if required_enrichments_for is None:
                # BACKWARD-COMPAT: 기존 applies_to 정적 매칭 (회귀 parity 기준선).
                selected = [e for e in enrichers if base.source_category in e.applies_to]
            else:
                # POLICY MODE: 종목별 required_enrichments (카테시안 곱: ticker × required).
                # enrichers 튜플 순서 보존 — applies_to 모드와 적용 순서 동일 (회귀 byte-parity).
                # 미등록 enricher name 은 매칭되는 enricher 가 없어 자연 skip.
                wanted = required_enrichments_for(base.ticker)
                selected = [e for e in enrichers if e.name in wanted]
            for enricher in selected:
                result = enricher.enrich(base, enrich_ctx)
                entry = entry.with_enrichment(enricher.name, result)
                if result.warnings:
                    all_warnings.extend(result.warnings)
                if result.skip_reason is None:
                    enriched_by[enricher.name] = enriched_by.get(enricher.name, 0) + 1
        enriched_entries.append(entry)

    by_category: dict[str, int] = {}
    for e in enriched_entries:
        by_category[e.source_category] = by_category.get(e.source_category, 0) + 1

    stats = {
        "total": len(enriched_entries),
        "by_source_category": by_category,
        "excluded": excluded_count,
        "dry_run": dry_run,
    }
    if degraded_sources:
        stats["degraded_sources"] = sorted(degraded_sources)
    if enriched_by:
        stats["enriched_by"] = dict(sorted(enriched_by.items()))

    return UniverseResult(
        entries=tuple(enriched_entries),
        warnings=tuple(all_warnings),
        skipped_sources=tuple(skipped),
        stats=stats,
    )


def _dedup(entries: list[UniverseEntry]) -> list[UniverseEntry]:
    """legacy ``merge_entries`` 와 동일 — (ticker, source_category, source_citation) key 보존."""
    out: list[UniverseEntry] = []
    seen: set[tuple[str, str, str]] = set()
    for e in entries:
        key = (e.ticker, e.source_category, e.source_citation)
        if key in seen:
            continue
        seen.add(key)
        out.append(e)
    return out
