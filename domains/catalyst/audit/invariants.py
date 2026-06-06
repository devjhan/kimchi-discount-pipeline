"""catalyst BC 고유 invariant — G7 citation 형식 검증 (runtime).

각 CatalystEvent 의 ``source_citation`` (+ metadata 의 additional_citations) 이 G7
형식인지 검사. 본 helper 는 재사용 가능한 순수 함수로, main 의 runtime invariant
wiring 에서 소비할 수 있다 (구 catalyst_scan 은 violation log 를 쓰지 않았으므로
정상 run 에서 catalyst-violations 파일은 생성되지 않는다 — behavior-preserving).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from domains._shared.audit.citation import is_valid_citation
from domains.catalyst.domain.event import CatalystEvent


@dataclass(frozen=True)
class CitationViolation:
    catalyst_id: str
    ticker: str
    bad_citations: tuple[str, ...]


def validate_g7_citations(events: Iterable[CatalystEvent]) -> list[CitationViolation]:
    """각 event 의 source_citation + additional_citations 중 G7 비적합 항목 수집.

    빈 source_citation 은 ignore (구 catalyst 도 빈 citation 강제 안 함).
    """
    out: list[CitationViolation] = []
    for e in events:
        bad: list[str] = []
        if e.source_citation and not is_valid_citation(e.source_citation):
            bad.append(e.source_citation)
        for c in e.metadata.get("additional_citations") or []:
            if isinstance(c, str) and c and not is_valid_citation(c):
                bad.append(c)
        if bad:
            out.append(
                CitationViolation(
                    catalyst_id=e.catalyst_id, ticker=e.ticker, bad_citations=tuple(bad)
                )
            )
    return out
