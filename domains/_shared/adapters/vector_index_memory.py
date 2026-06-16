"""InMemoryVectorIndex — VectorIndexPort 의 순수 in-memory 구현 (의존성 0).

용도: (1) 단위테스트의 결정론적 stub, (2) 벡터 저장소 미가용 시 graceful fallback,
(3) resolver 의 reference 구현. ``infrastructure`` import 0 — 순수 알고리즘이라
``_shared/adapters`` 거주 (``disclosure_scan`` 과 동일 tier).

sqlite 백엔드(``infrastructure/vectorstore``)와 동일 cosine/top_k 시맨틱 — 둘은 동일
VectorIndexPort 계약을 만족한다. cosine 함수는 소형이라 의도적으로 복제(rule-of-three
미충족, infra↛domains 제약상 공유 모듈 불가).
"""
from __future__ import annotations

import math
from typing import Any, Mapping, Sequence


def _cosine(a: Sequence[float], b: Sequence[float]) -> float | None:
    if not a or not b or len(a) != len(b):
        return None
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return None
    return dot / (na * nb)


class InMemoryVectorIndex:
    """dict 기반 VectorIndexPort 구현. 영속성 없음 (프로세스 수명)."""

    def __init__(self) -> None:
        # (kind, key) -> {"vector":[...], "model_id":..., "text_hash":...}
        self._vectors: dict[tuple[str, str], dict[str, Any]] = {}
        self._scalars: dict[str, dict[str, Any]] = {}

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
        self._vectors[(kind, key)] = {
            "vector": [float(x) for x in vector],
            "model_id": model_id,
            "text_hash": text_hash,
            "embedded_at": embedded_at,
        }

    def has_fresh_vector(
        self, *, kind: str, key: str, model_id: str, text_hash: str
    ) -> bool:
        rec = self._vectors.get((kind, key))
        return bool(
            rec and rec["model_id"] == model_id and rec["text_hash"] == text_hash
        )

    def upsert_scalars(self, ticker: str, scalars: Mapping[str, Any]) -> None:
        self._scalars.setdefault(ticker, {}).update(scalars)

    def cosine(self, ticker: str, concept: str) -> float | None:
        tv = self._vectors.get(("ticker", ticker))
        cv = self._vectors.get(("concept", concept))
        if tv is None or cv is None:
            return None
        return _cosine(tv["vector"], cv["vector"])

    def get_vector(self, kind: str, key: str) -> list[float] | None:
        rec = self._vectors.get((kind, key))
        return list(rec["vector"]) if rec else None

    def top_k(self, concept: str, k: int) -> list[tuple[str, float]]:
        cv = self._vectors.get(("concept", concept))
        if cv is None or k < 1:
            return []
        scored: list[tuple[str, float]] = []
        for (kind, key), rec in self._vectors.items():
            if kind != "ticker":
                continue
            sim = _cosine(rec["vector"], cv["vector"])
            if sim is not None:
                scored.append((key, sim))
        scored.sort(key=lambda kv: kv[1], reverse=True)
        return scored[:k]

    def attributes_for(self, ticker: str) -> Mapping[str, Any]:
        return dict(self._scalars.get(ticker, {}))
