"""build_segment_index — 벡터 인덱스 build 오케스트레이션 (순수, 주입형 ports).

per-ticker 텍스트 + concept(anchor 또는 seed-centroid)를 임베딩해 VectorIndexPort 에 적재
하고, scalar 선택 속성을 upsert 한다. 모든 외부 의존(EmbeddingPort / VectorIndexPort /
텍스트·scalar source)은 **주입** — 본 모듈은 infra 를 import 하지 않는다 (bc-independent,
단위테스트 가능). 실제 wiring(텍스트=DART MD&A, scalar=KIS/universe, 경로)은 consumer
composition root.

- embed-once: 동일 (model_id, text_hash) ticker/anchor 벡터가 있으면 재임베딩 skip (결정성/
  비용). seed 인 ticker 는 centroid 산식을 위해 항상 임베딩(소수라 비용 무시).
- seed-centroid (Task 6 / §4 1-a): seed_tickers 를 가진 concept 의 벡터 = seed 종목 임베딩
  의 **centroid** (ticker 와 동일 장르 → 직접 cosine 비교로 코호트 분리). seed 가 universe
  밖이면 그 텍스트도 임베딩 대상에 포함하되 **ticker 벡터로는 적재하지 않는다**(top_k 오염
  방지). seed 벡터 0개 → concept 미적재 + warning (G8 날조 금지). anchor_text-only concept
  는 backward-compat (anchor 텍스트 임베딩).
- graceful (G8/G11): 임베딩 status != 'ok' → 벡터 미적재 + warning. scalar 는 임베딩과
  독립적으로 항상 적재 (rule-based 선택은 계속 동작).
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


def _centroid(vectors: Sequence[Sequence[float]]) -> list[float]:
    """동일 차원 벡터들의 산술 평균(centroid). 호출부가 비어있지 않음을 보장.

    차원이 다른 벡터(동일 모델이면 미발생)는 방어적으로 제외. 모두 제외되면 [] 반환.
    """
    dim = len(vectors[0])
    acc = [0.0] * dim
    n = 0
    for v in vectors:
        if len(v) != dim:
            continue
        for i in range(dim):
            acc[i] += float(v[i])
        n += 1
    return [x / n for x in acc] if n else []


def _seed_centroid_hash(concept_id: str, present_seed_texts: Mapping[str, str]) -> str:
    """seed-centroid concept 벡터의 staleness/provenance 키 — 사용된 seed+텍스트 해시."""
    parts = [f"{s}:{text_hash(present_seed_texts[s])}" for s in sorted(present_seed_texts)]
    return text_hash(f"centroid::{concept_id}::" + "|".join(parts))


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

    concepts = list(concepts)
    seed_concepts = [c for c in concepts if c.seed_tickers]
    anchor_concepts = [c for c in concepts if not c.seed_tickers]

    # ---- per-ticker scalar upsert + 텍스트 수집 ----
    ticker_texts: dict[str, str] = {}
    for ticker in tickers:
        scalars = dict(scalars_for(ticker))
        if scalars:
            vector_index.upsert_scalars(ticker, scalars)
            scalars_written += 1
        text = (text_for(ticker) or "").strip()
        if text:
            ticker_texts[ticker] = text
        else:
            warnings.append(f"{ticker}: 텍스트 부재 — 임베딩 skip")

    # ---- seed 텍스트 수집 (centroid 용). universe 밖 seed 도 포함 (그 MD&A 임베딩). ----
    seed_texts: dict[str, str] = {}
    for c in seed_concepts:
        for seed in c.seed_tickers:
            if seed in seed_texts:
                continue
            text = (ticker_texts.get(seed) or text_for(seed) or "").strip()
            if text:
                seed_texts[seed] = text

    # ---- anchor-only concept 텍스트 (backward-compat) ----
    anchor_texts: dict[str, str] = {}
    for c in anchor_concepts:
        text = c.anchor_text.strip()
        if text:
            anchor_texts[c.concept_id] = text
        else:  # schema 가 anchor_text 또는 seed_tickers 를 보장하므로 사실상 도달 불가
            warnings.append(f"concept {c.concept_id}: anchor_text 비어 — 임베딩 skip")

    # ---- 임베딩 대상 결정 (text_hash 단위 dedup) ----
    pending: dict[str, str] = {}  # text_hash -> text

    ticker_store: list[tuple[str, str]] = []  # (ticker, text) — ticker 벡터로 적재할 것
    for ticker, text in ticker_texts.items():
        h = text_hash(text)
        # seed 인 ticker 는 centroid 용 벡터가 필요하므로 staleness skip 대상에서 제외.
        if ticker not in seed_texts and vector_index.has_fresh_vector(
            kind="ticker", key=ticker, model_id=model_id, text_hash=h
        ):
            skipped_fresh += 1
            continue
        ticker_store.append((ticker, text))
        pending[h] = text

    anchor_store: list[tuple[str, str]] = []  # (concept_id, text)
    for cid, text in anchor_texts.items():
        h = text_hash(text)
        if vector_index.has_fresh_vector(
            kind="concept", key=cid, model_id=model_id, text_hash=h
        ):
            skipped_fresh += 1
            continue
        anchor_store.append((cid, text))
        pending[h] = text

    # seed 텍스트는 centroid 산식을 위해 항상 임베딩 (소수 seed — 비용 무시 가능).
    for text in seed_texts.values():
        pending[text_hash(text)] = text

    # ---- 배치 임베딩 (1회) ----
    vec_by_hash: dict[str, list[float]] = {}
    embedding_skipped = False
    embedded_model = model_id
    if pending:
        texts: Sequence[str] = list(pending.values())
        result = embedding.embed(texts)
        if result.status != "ok":
            warnings.append(
                f"임베딩 {result.status}: {result.skip_reason or result.error or ''} "
                f"— {len(texts)}건 벡터 미적재 (semantic UNKNOWN)"
            )
            embedding_skipped = True
        else:
            embedded_model = result.model_id or model_id
            for text, vec in zip(texts, result.vectors, strict=False):
                vec_by_hash[text_hash(text)] = [float(x) for x in vec]

    n_ticker = 0
    n_concept = 0
    if not embedding_skipped:
        # ticker 벡터 적재.
        for ticker, text in ticker_store:
            vec = vec_by_hash.get(text_hash(text))
            if vec is None:
                continue
            vector_index.upsert_vector(
                kind="ticker", key=ticker, vector=vec,
                model_id=embedded_model, text_hash=text_hash(text), embedded_at=now_iso,
            )
            n_ticker += 1

        # anchor-only concept 벡터 적재 (backward-compat).
        for cid, text in anchor_store:
            vec = vec_by_hash.get(text_hash(text))
            if vec is None:
                continue
            vector_index.upsert_vector(
                kind="concept", key=cid, vector=vec,
                model_id=embedded_model, text_hash=text_hash(text), embedded_at=now_iso,
            )
            n_concept += 1

        # seed-centroid concept 벡터 적재.
        for c in seed_concepts:
            seed_vecs: list[list[float]] = []
            present: dict[str, str] = {}
            missing: list[str] = []
            for seed in c.seed_tickers:
                stext = seed_texts.get(seed)
                vec = vec_by_hash.get(text_hash(stext)) if stext else None
                if vec is None:
                    missing.append(seed)
                else:
                    seed_vecs.append(vec)
                    present[seed] = stext
            if not seed_vecs:
                warnings.append(
                    f"concept {c.concept_id}: seed 벡터 0개 — concept 미적재 (G8 날조 금지)"
                )
                continue
            if missing:
                warnings.append(
                    f"concept {c.concept_id}: seed 텍스트 부재 {missing} — "
                    f"가용 seed {len(seed_vecs)}개로 centroid"
                )
            vector_index.upsert_vector(
                kind="concept", key=c.concept_id, vector=_centroid(seed_vecs),
                model_id=embedded_model,
                text_hash=_seed_centroid_hash(c.concept_id, present),
                embedded_at=now_iso,
            )
            n_concept += 1

    return BuildReport(
        model_id=model_id,
        embedded_tickers=n_ticker,
        embedded_concepts=n_concept,
        skipped_fresh=skipped_fresh,
        scalars_written=scalars_written,
        embedding_skipped=embedding_skipped,
        warnings=tuple(warnings),
    )
