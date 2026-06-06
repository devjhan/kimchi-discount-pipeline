"""EnrichedEntry — UniverseEntry + per-enricher attached attributes.

설계 원칙:
- base UniverseEntry 의 모든 필드를 그대로 top-level 노출 → downstream readers
  (catalyst_scan / screener.io.universe_loader / brief_gate) 가 ``entry.ticker``,
  ``entry.source_category`` 등 기존 contract 그대로 사용. 신규 enrichment field 만
  추가 — 호환 보장.
- ``enrichments`` 는 ``enricher_name → attributes Mapping`` 의 dict — opt-in 으로
  사용. 예: ``entry.enrichments["nav_discount"]["discount_pct"]``.
- enrichment 의 citations / warnings / skip_reason 은 별도 필드로 격리 → base
  source 의 citation / warning 과 mixing 금지.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from domains.universe.domain.entry import UniverseEntry


@dataclass(frozen=True)
class EnrichmentResult:
    """단일 enricher 의 enrich() 산출."""

    attributes: Mapping[str, Any]
    """enricher 가 attach 하는 attribute dict (envelope 의 enrichments[name] 값)."""

    citations: tuple[str, ...] = ()
    """G7 형식 citation list (KIS@ts=..., Yahoo@ts=..., DART@ts=... 등)."""

    warnings: tuple[str, ...] = ()
    """human-readable 진단 메시지 (G8 graceful degradation 추적)."""

    skip_reason: str | None = None
    """non-None 이면 enrichment 가 실행되지 못함 (e.g., API 키 부재 / 매핑 부재).
    attributes 는 빈 dict 권장.
    """


@dataclass(frozen=True)
class EnrichedEntry:
    """UniverseEntry + 0+ enricher 의 attached attributes.

    base 필드 (ticker / name / source_category / inclusion_reason / fetched_at /
    source_citation / metadata) 는 downstream 호환 보장 — 기존 readers 그대로 동작.
    """

    ticker: str
    name: str
    source_category: str
    inclusion_reason: str
    fetched_at: str
    source_citation: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    enrichments: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    """{enricher_name: attributes_mapping}. opt-in 으로 사용."""

    enrichment_citations: tuple[str, ...] = ()
    """모든 enricher citation 의 union (dedup 보존 순서)."""

    enrichment_warnings: tuple[str, ...] = ()
    """모든 enricher warning 의 union."""

    enrichment_skips: Mapping[str, str] = field(default_factory=dict)
    """{enricher_name: skip_reason} — enrichment 가 실패한 enricher 만 등록."""

    @classmethod
    def from_base(cls, base: UniverseEntry) -> "EnrichedEntry":
        """UniverseEntry → enrichments 없는 EnrichedEntry. enrich() 가 본 객체에 attach."""
        return cls(
            ticker=base.ticker,
            name=base.name,
            source_category=base.source_category,
            inclusion_reason=base.inclusion_reason,
            fetched_at=base.fetched_at,
            source_citation=base.source_citation,
            metadata=base.metadata,
        )

    def with_enrichment(
        self, name: str, result: EnrichmentResult
    ) -> "EnrichedEntry":
        """본 entry 에 단일 enricher 의 결과를 attach (frozen — 새 instance 반환)."""
        new_enrichments = dict(self.enrichments)
        new_skips = dict(self.enrichment_skips)
        if result.skip_reason is not None:
            new_skips[name] = result.skip_reason
        else:
            new_enrichments[name] = result.attributes
        # citations / warnings dedup 보존 순서
        new_citations = _dedup_preserving(self.enrichment_citations + result.citations)
        new_warnings = _dedup_preserving(self.enrichment_warnings + result.warnings)
        return EnrichedEntry(
            ticker=self.ticker,
            name=self.name,
            source_category=self.source_category,
            inclusion_reason=self.inclusion_reason,
            fetched_at=self.fetched_at,
            source_citation=self.source_citation,
            metadata=self.metadata,
            enrichments=new_enrichments,
            enrichment_citations=new_citations,
            enrichment_warnings=new_warnings,
            enrichment_skips=new_skips,
        )


def _dedup_preserving(items: tuple[str, ...]) -> tuple[str, ...]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return tuple(out)
