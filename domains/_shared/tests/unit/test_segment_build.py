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


# ----------------------------------------------------------------------
# seed-centroid concept anchor (Task 6 / §4 1-a)
# ----------------------------------------------------------------------
def _seed_concept(seed_tickers, *, anchor_text="", cid="holdco"):
    return ConceptDeclaration(
        concept_id=cid,
        schema_version=CONCEPT_SCHEMA_VERSION,
        concept_version=2,
        anchor_text=anchor_text,
        seed_tickers=tuple(seed_tickers),
        default_threshold=0.5,
    )


def _mapped_embedding(mapping, *, model="fake-model", dim=2):
    """text → vector 결정론 transport (centroid 산식 검증용)."""

    def _transport(texts):
        return [list(mapping[t]) for t in texts], model, dim

    return RemoteEmbeddingAdapter(transport=_transport, model_id=model)


@pytest.mark.unit
def test_seed_centroid_is_mean_of_seed_vectors() -> None:
    idx = InMemoryVectorIndex()
    mapping = {"text1": [1.0, 0.0], "text2": [0.0, 1.0]}
    report = build_segment_index(
        tickers=["KR:001", "KR:002"],
        text_for=lambda t: {"KR:001": "text1", "KR:002": "text2"}[t],
        scalars_for=_scalars({}),
        concepts=[_seed_concept(["KR:001", "KR:002"])],
        embedding=_mapped_embedding(mapping),
        vector_index=idx,
        now_iso="t",
    )
    assert report.embedded_concepts == 1
    assert report.embedded_tickers == 2
    # concept 벡터 = seed 벡터들의 산술 평균.
    assert idx.get_vector("concept", "holdco") == pytest.approx([0.5, 0.5])
    # seed(=universe ticker) 벡터는 그대로 적재.
    assert idx.get_vector("ticker", "KR:001") == pytest.approx([1.0, 0.0])


@pytest.mark.unit
def test_seed_not_in_universe_is_embedded_but_not_stored_as_ticker() -> None:
    idx = InMemoryVectorIndex()
    mapping = {"text1": [1.0, 0.0], "textout": [0.0, 1.0]}
    report = build_segment_index(
        tickers=["KR:001"],  # KR:OUT 은 universe 밖
        text_for=lambda t: {"KR:001": "text1", "KR:OUT": "textout"}[t],
        scalars_for=_scalars({}),
        concepts=[_seed_concept(["KR:001", "KR:OUT"])],
        embedding=_mapped_embedding(mapping),
        vector_index=idx,
        now_iso="t",
    )
    # universe 밖 seed 도 centroid 에 포함 (평균 = [0.5, 0.5]).
    assert idx.get_vector("concept", "holdco") == pytest.approx([0.5, 0.5])
    # 그러나 ticker 벡터로는 적재하지 않는다 (top_k 오염 방지).
    assert idx.get_vector("ticker", "KR:OUT") is None
    assert ("KR:OUT" not in [t for t, _ in idx.top_k("holdco", 10)])
    assert report.embedded_tickers == 1  # KR:001 만 ticker 벡터


@pytest.mark.unit
def test_seed_concept_empty_seeds_degrades_with_warning() -> None:
    idx = InMemoryVectorIndex()
    report = build_segment_index(
        tickers=[],  # 빈 universe → seed 텍스트도 부재
        text_for=lambda t: "",
        scalars_for=_scalars({}),
        concepts=[_seed_concept(["KR:NOPE"])],
        embedding=_mapped_embedding({}),
        vector_index=idx,
        now_iso="t",
    )
    # seed 벡터 0개 → concept 미적재 (G8 날조 금지) + warning.
    assert idx.get_vector("concept", "holdco") is None
    assert report.embedded_concepts == 0
    assert any("seed 벡터 0개" in w for w in report.warnings)


@pytest.mark.unit
def test_seed_centroid_with_partial_missing_seed_uses_available() -> None:
    idx = InMemoryVectorIndex()
    mapping = {"text1": [1.0, 0.0], "text2": [3.0, 0.0]}
    report = build_segment_index(
        tickers=["KR:001", "KR:002"],
        # KR:MISSING 은 텍스트 부재 → centroid 에서 제외, 가용 seed 로 산출.
        text_for=lambda t: {"KR:001": "text1", "KR:002": "text2", "KR:MISSING": ""}[t],
        scalars_for=_scalars({}),
        concepts=[_seed_concept(["KR:001", "KR:002", "KR:MISSING"])],
        embedding=_mapped_embedding(mapping),
        vector_index=idx,
        now_iso="t",
    )
    assert report.embedded_concepts == 1
    assert idx.get_vector("concept", "holdco") == pytest.approx([2.0, 0.0])  # (1+3)/2
    assert any("seed 텍스트 부재" in w for w in report.warnings)


@pytest.mark.unit
def test_seed_concept_takes_precedence_over_anchor_text() -> None:
    # seed_tickers 가 있으면 concept 벡터는 centroid (anchor_text 는 무시되고 벡터에 미반영).
    idx = InMemoryVectorIndex()
    mapping = {"seedtext": [1.0, 0.0], "anchor!!!": [0.0, 1.0]}
    build_segment_index(
        tickers=["KR:001"],
        text_for=lambda t: {"KR:001": "seedtext"}[t],
        scalars_for=_scalars({}),
        concepts=[_seed_concept(["KR:001"], anchor_text="anchor!!!")],
        embedding=_mapped_embedding(mapping),
        vector_index=idx,
        now_iso="t",
    )
    # centroid([1,0]) — anchor "anchor!!!"([0,1]) 가 아니라 seed 벡터.
    assert idx.get_vector("concept", "holdco") == pytest.approx([1.0, 0.0])
