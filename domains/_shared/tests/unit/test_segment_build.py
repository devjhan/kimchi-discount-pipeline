"""segment_registry.build — build_segment_index 단위 테스트 (Task 9)."""
from __future__ import annotations

import pytest

from domains._shared.adapters.embedding_remote import RemoteEmbeddingAdapter
from domains._shared.adapters.vector_index_memory import InMemoryVectorIndex
from domains._shared.segment_registry.build import build_segment_index, text_hash
from domains._shared.segment_registry.concepts import (
    CONCEPT_SCHEMA_VERSION,
    ConceptDeclaration,
)


def _concept() -> ConceptDeclaration:
    return ConceptDeclaration(
        concept_id="holdco",
        schema_version=CONCEPT_SCHEMA_VERSION,
        concept_version=1,
        anchor_text="지주사 NAV 할인",
        default_threshold=0.7,
    )


def _ok_embedding():
    return RemoteEmbeddingAdapter(
        transport=lambda texts: ([[0.1, 0.2, 0.3] for _ in texts], "fake-model", 3),
        model_id="fake-model",
    )


def _scalars(mapping):
    return lambda t: mapping.get(t, {})


@pytest.mark.unit
def test_build_populates_vectors_and_scalars() -> None:
    idx = InMemoryVectorIndex()
    report = build_segment_index(
        tickers=["KR:003550", "KR:000880"],
        text_for=lambda t: f"text for {t}",
        scalars_for=_scalars({"KR:003550": {"market_cap_krw": 5e11}}),
        concepts=[_concept()],
        embedding=_ok_embedding(),
        vector_index=idx,
        now_iso="2026-06-12T00:00:00+09:00",
    )
    assert report.embedded_concepts == 1
    assert report.embedded_tickers == 2
    assert report.scalars_written == 1
    assert idx.cosine("KR:003550", "holdco") is not None
    assert idx.attributes_for("KR:003550")["market_cap_krw"] == 5e11


@pytest.mark.unit
def test_build_staleness_skips_fresh() -> None:
    idx = InMemoryVectorIndex()
    # 이미 동일 (model, text_hash) 적재
    idx.upsert_vector(
        kind="ticker", key="KR:003550", vector=[0.0, 0.0, 0.0],
        model_id="fake-model", text_hash=text_hash("text for KR:003550"),
        embedded_at="t",
    )
    report = build_segment_index(
        tickers=["KR:003550"],
        text_for=lambda t: f"text for {t}",
        scalars_for=_scalars({}),
        concepts=[],
        embedding=_ok_embedding(),
        vector_index=idx,
        now_iso="t",
    )
    assert report.skipped_fresh == 1
    assert report.embedded_tickers == 0


@pytest.mark.unit
def test_build_embedding_unavailable_degrades_but_writes_scalars() -> None:
    idx = InMemoryVectorIndex()
    unavailable = RemoteEmbeddingAdapter(
        transport=lambda texts: ([], "m", 0), model_id="m", available=False
    )
    report = build_segment_index(
        tickers=["KR:003550"],
        text_for=lambda t: "some text",
        scalars_for=_scalars({"KR:003550": {"source_category": "holding_company"}}),
        concepts=[_concept()],
        embedding=unavailable,
        vector_index=idx,
        now_iso="t",
    )
    assert report.embedding_skipped is True
    assert report.embedded_tickers == 0
    # scalar 는 임베딩과 독립적으로 적재됨 (rule-based 선택 계속 동작)
    assert report.scalars_written == 1
    assert idx.attributes_for("KR:003550")["source_category"] == "holding_company"
    # 벡터는 미적재 → cosine None (semantic UNKNOWN downstream)
    assert idx.cosine("KR:003550", "holdco") is None
    assert any("임베딩 skipped" in w for w in report.warnings)
