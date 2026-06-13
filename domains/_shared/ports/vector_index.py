"""VectorIndexPort — 임베디드 벡터 저장/질의 seam (순수 typing, infra import 0).

구현(adapter)은 ``infrastructure/vectorstore/`` 의 ``sqlite-vec`` 백엔드 (11-b/13-a).
kernel(SegmentResolver / build 단계)은 본 Protocol 에만 의존하고 composition root 가
adapter 를 주입한다. 벡터는 모델 버전 의존 *재생성 불가 증거* → telemetry 거주
(ADR-0008). scalar 선택 속성은 같은 store 에 동거 (단일 sqlite 파일).

키 규약: ticker 벡터는 ``kind='ticker'`` + ``key='KR:NNNNNN'``; concept anchor 는
``kind='concept'`` + ``key=<concept_id>``. ``cosine(ticker, concept)`` 은 둘 사이 코사인.
"""
from __future__ import annotations

from typing import Any, Mapping, Protocol, Sequence, runtime_checkable


@runtime_checkable
class VectorIndexPort(Protocol):
    """벡터 + scalar 선택 속성의 임베디드 저장/질의."""

    def upsert_vector(
        self,
        *,
        kind: str,
        key: str,
        vector: Sequence[float],
        model_id: str,
        text_hash: str,
        embedded_at: str,
    ) -> None:
        """단일 벡터 upsert (kind='ticker'|'concept'). 메타(model/text_hash/ts) 동반."""
        ...

    def has_fresh_vector(
        self, *, kind: str, key: str, model_id: str, text_hash: str
    ) -> bool:
        """동일 (model_id, text_hash) 벡터가 이미 있나 — embed-once / staleness 판정."""
        ...

    def upsert_scalars(self, ticker: str, scalars: Mapping[str, Any]) -> None:
        """ticker 의 scalar 선택 속성 upsert (market_cap_krw / source_category 등)."""
        ...

    def cosine(self, ticker: str, concept: str) -> float | None:
        """ticker 벡터 vs concept anchor 벡터 코사인. 둘 중 하나라도 부재 → None."""
        ...

    def top_k(self, concept: str, k: int) -> list[tuple[str, float]]:
        """concept anchor 에 가장 가까운 ticker top-k [(ticker, cosine), ...] 내림차순."""
        ...

    def attributes_for(self, ticker: str) -> Mapping[str, Any]:
        """ticker 의 적재된 scalar 선택 속성 dict. 부재 → 빈 dict."""
        ...
