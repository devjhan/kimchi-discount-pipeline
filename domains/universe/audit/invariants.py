"""Universe invariants — runtime audit checks.

screener ``domains/screener/audit/invariants.py`` 와 동등 layer. 차이:
- screener 는 build-time invariant (HardGuardWrapper override 차단 등) 중심
- universe 는 runtime invariant (G7 citation, source_category 일관성) 중심

invariants:

- **G7 — 모든 attribute citation**: ``EnrichedEntry.source_citation`` +
  ``enrichment_citations`` 가 ``{SOURCE}@{ts}={value}`` 정규식 매칭. 위반 시
  severity="warning" GuardViolation 기록 (run 자체는 진행).

- **source_category consistency**: ``Enricher.applies_to`` 가 sources.yaml 의
  실제 source_category 집합의 subset. 미매칭 enricher 는 사실상 dead code →
  warning 발행 (blocking 아님; orphan enricher 도 무해).

G6 (산식은 enricher / source 내부에서만) 와 G14 (manual map 외 자동 추가 금지)
는 코드 리뷰 차원의 컨벤션 — runtime 가시 신호 부재. ``.guidelines/04-audit.md``
참조.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from domains.universe.audit.citation import is_valid_citation
from domains.universe.domain.enriched import EnrichedEntry


@dataclass(frozen=True)
class CitationViolation:
    """단일 entry 의 잘못된 citation 1건."""

    ticker: str
    source_category: str
    bad_citations: tuple[str, ...]


def validate_g7_citations(entries: Iterable[EnrichedEntry]) -> list[CitationViolation]:
    """G7 — 각 entry 의 source_citation + enrichment_citations 검증.

    return: 1+ malformed citation 가진 entries 의 list (정상 entries 는 결과 미포함).
    """
    out: list[CitationViolation] = []
    for entry in entries:
        bad: list[str] = []
        if entry.source_citation and not is_valid_citation(entry.source_citation):
            bad.append(entry.source_citation)
        for c in entry.enrichment_citations:
            if not is_valid_citation(c):
                bad.append(c)
        if bad:
            out.append(
                CitationViolation(
                    ticker=entry.ticker,
                    source_category=entry.source_category,
                    bad_citations=tuple(bad),
                )
            )
    return out


def validate_enricher_applies_to(
    enricher_applies_to: dict[str, frozenset[str]],
    source_categories_in_use: frozenset[str],
) -> list[str]:
    """source_category consistency — orphan enricher 명시.

    Args:
        enricher_applies_to: ``{enricher_name: applies_to_set}``
        source_categories_in_use: sources.yaml build 결과의 source_category 집합

    Returns:
        ``enricher_name`` list — applies_to 가 source_categories_in_use 와 disjoint
        한 enricher 들 (해당 entries 가 없어 dead code).
    """
    orphans: list[str] = []
    for name, applies_to in enricher_applies_to.items():
        if not (applies_to & source_categories_in_use):
            orphans.append(name)
    return orphans
