"""build_segment_index — 벡터 인덱스 build 오케스트레이션 (순수, 주입형 ports).

per-ticker 텍스트 + concept anchor 텍스트를 임베딩해 VectorIndexPort 에 적재하고, scalar
선택 속성을 upsert 한다. 모든 외부 의존(EmbeddingPort / VectorIndexPort / 텍스트·scalar
source)은 **주입** — 본 모듈은 infra 를 import 하지 않는다 (bc-independent, 단위테스트
가능). 실제 wiring(텍스트=DART, scalar=KIS/universe, 경로)은 consumer composition root.

- embed-once: 동일 (model_id, text_hash) 벡터가 있으면 재임베딩 skip (결정성/비용).
- graceful (G8/G11): 임베딩 status != 'ok' → 벡터 미적재 + warning (날조 금지). scalar 는
  임베딩과 독립적으로 항상 적재 (rule-based 선택은 계속 동작).
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Mapping, Sequence

from domains._shared.ports.embedding import EmbeddingPort
from domains._shared.segment_registry.concepts import ConceptDeclaration

TextFor = Callable[[str], str]
ScalarsFor = Callable[[str], Mapping[str, Any]]


def text_hash(text: str) -> str:
    """임베딩 staleness 키 — 텍스트 내용 해시 (앞 16 hex)."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


@dataclass
class BuildReport:
    """build 1회 산출 요약."""

    model_id: str = ""
    embedded_tickers: int = 0
    embedded_concepts: int = 0
    skipped_fresh: int = 0
    scalars_written: int = 0
    embedding_skipped: bool = False
    warnings: tuple[str, ...] = field(default_factory=tuple)


def _embed_items(
    items: list[tuple[str, str, str]],  # (kind, key, text)
    *,
    embedding: EmbeddingPort,
    vector_index: Any,
    now_iso: str,
    warnings: list[str],
) -> tuple[int, int, bool]:
    """fresh 하지 않은 (kind,key,text) 들을 배치 임베딩 후 upsert. (ticker수, concept수, skipped)."""
    if not items:
        return 0, 0, False
    texts: Sequence[str] = [t for _, _, t in items]
    result = embedding.embed(texts)
    if result.status != "ok":
        warnings.append(
            f"임베딩 {result.status}: {result.skip_reason or result.error or ''} "
            f"— {len(items)}건 벡터 미적재 (semantic UNKNOWN)"
        )
        return 0, 0, True
    n_ticker = n_concept = 0
    for (kind, key, text), vec in zip(items, result.vectors):
        vector_index.upsert_vector(
            kind=kind,
            key=key,
            vector=vec,
            model_id=result.model_id,
            text_hash=text_hash(text),
            embedded_at=now_iso,
        )
        if kind == "ticker":
            n_ticker += 1
        else:
            n_concept += 1
    return n_ticker, n_concept, False


def build_segment_index(
    *,
    tickers: Iterable[str],
    text_for: TextFor,
    scalars_for: ScalarsFor,
    concepts: Iterable[ConceptDeclaration],
    embedding: EmbeddingPort,
    vector_index: Any,
    now_iso: str,
) -> BuildReport:
    """벡터 인덱스 build. 모든 의존 주입. 반환: BuildReport."""
    warnings: list[str] = []
    model_id = embedding.model_id
    skipped_fresh = 0
    scalars_written = 0

    pending: list[tuple[str, str, str]] = []  # (kind, key, text)

    # concept anchors
    for c in concepts:
        text = c.anchor_text.strip()
        if not text:
            warnings.append(f"concept {c.concept_id}: anchor_text 비어 — 임베딩 skip (seed-only)")
            continue
        if vector_index.has_fresh_vector(
            kind="concept", key=c.concept_id, model_id=model_id, text_hash=text_hash(text)
        ):
            skipped_fresh += 1
            continue
        pending.append(("concept", c.concept_id, text))

    # per-ticker
    for ticker in tickers:
        scalars = dict(scalars_for(ticker))
        if scalars:
            vector_index.upsert_scalars(ticker, scalars)
            scalars_written += 1
        text = (text_for(ticker) or "").strip()
        if not text:
            warnings.append(f"{ticker}: 텍스트 부재 — 임베딩 skip")
            continue
        if vector_index.has_fresh_vector(
            kind="ticker", key=ticker, model_id=model_id, text_hash=text_hash(text)
        ):
            skipped_fresh += 1
            continue
        pending.append(("ticker", ticker, text))

    n_ticker, n_concept, emb_skipped = _embed_items(
        pending,
        embedding=embedding,
        vector_index=vector_index,
        now_iso=now_iso,
        warnings=warnings,
    )

    return BuildReport(
        model_id=model_id,
        embedded_tickers=n_ticker,
        embedded_concepts=n_concept,
        skipped_fresh=skipped_fresh,
        scalars_written=scalars_written,
        embedding_skipped=emb_skipped,
        warnings=tuple(warnings),
    )
