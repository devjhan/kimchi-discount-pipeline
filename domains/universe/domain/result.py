"""UniverseResult — build_universe orchestrator 산출 묶음.

frozen value object. main.py 가 본 객체를 envelope 으로 변환해 trail 에 write.

Run 5: entries 가 ``EnrichedEntry`` (이전: ``UniverseEntry``). 호환 보장 — base
필드 (ticker / name / source_category / ...) 는 그대로 top-level 노출되며 enrichments
는 신규 ``enrichments`` 필드로 추가.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from domains.universe.domain.enriched import EnrichedEntry


@dataclass(frozen=True)
class SkippedSource:
    """source 가 entries 0개 + warning 1개 이상 산출 시 본 객체로 요약."""

    source: str
    reason: str


@dataclass(frozen=True)
class UniverseResult:
    """단일 build_universe() 호출의 산출.

    - ``entries`` — exclusions 적용 + enrichment 완료 후 최종 EnrichedEntry tuple
    - ``warnings`` — 모든 source / enrichment warnings 의 합
    - ``skipped_sources`` — 0 entries + warning 인 source 의 요약 (debug 용)
    - ``stats`` — envelope 의 ``stats`` 필드 (total / by_source_category / excluded /
      dry_run / degraded_sources / enriched_by[enricher_name])
    """

    entries: tuple[EnrichedEntry, ...]
    warnings: tuple[str, ...]
    skipped_sources: tuple[SkippedSource, ...]
    stats: dict[str, Any] = field(default_factory=dict)
