"""segment_registry — InMemoryVectorIndex (VectorIndexPort) 단위 테스트 (Task 4)."""
from __future__ import annotations

import pytest

from domains._shared.adapters.vector_index_memory import InMemoryVectorIndex
from domains._shared.ports.vector_index import VectorIndexPort


def _seed() -> InMemoryVectorIndex:
    idx = InMemoryVectorIndex()
    meta = dict(model_id="m", embedded_at="2026-06-12T00:00:00+09:00")
    idx.upsert_vector(kind="concept", key="holdco", vector=[1.0, 0.0], text_hash="c", **meta)
    idx.upsert_vector(kind="ticker", key="KR:A", vector=[1.0, 0.0], text_hash="a", **meta)
    idx.upsert_vector(kind="ticker", key="KR:B", vector=[0.0, 1.0], text_hash="b", **meta)
    idx.upsert_vector(kind="ticker", key="KR:C", vector=[0.7, 0.7], text_hash="cc", **meta)
    return idx


@pytest.mark.unit
def test_is_vector_index_port() -> None:
    assert isinstance(InMemoryVectorIndex(), VectorIndexPort)


@pytest.mark.unit
def test_cosine_aligned_is_one() -> None:
    idx = _seed()
    assert idx.cosine("KR:A", "holdco") == pytest.approx(1.0)
    assert idx.cosine("KR:B", "holdco") == pytest.approx(0.0)


@pytest.mark.unit
def test_cosine_missing_returns_none() -> None:
    idx = _seed()
    assert idx.cosine("KR:NONE", "holdco") is None
    assert idx.cosine("KR:A", "ghost") is None


@pytest.mark.unit
def test_top_k_ordering() -> None:
    idx = _seed()
    top = idx.top_k("holdco", 2)
    assert [k for k, _ in top] == ["KR:A", "KR:C"]
    assert top[0][1] >= top[1][1]


@pytest.mark.unit
def test_scalars_roundtrip_merge() -> None:
    idx = _seed()
    idx.upsert_scalars("KR:A", {"market_cap_krw": 5e11})
    idx.upsert_scalars("KR:A", {"source_category": "holding_company"})
    attrs = idx.attributes_for("KR:A")
    assert attrs["market_cap_krw"] == 5e11
    assert attrs["source_category"] == "holding_company"
    assert idx.attributes_for("KR:NONE") == {}


@pytest.mark.unit
def test_staleness_check() -> None:
    idx = _seed()
    assert idx.has_fresh_vector(kind="ticker", key="KR:A", model_id="m", text_hash="a")
    assert not idx.has_fresh_vector(kind="ticker", key="KR:A", model_id="m", text_hash="CHANGED")
    assert not idx.has_fresh_vector(kind="ticker", key="KR:A", model_id="m2", text_hash="a")
