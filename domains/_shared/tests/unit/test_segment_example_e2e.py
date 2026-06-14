"""segment_registry — 예시 governance 선언 end-to-end resolve (Task 12 / integration).

실제 ``governance/policy/concepts``·``segment_profiles``·``segments`` 의 예시 파일을 레지스트리로
로드해 SelectorEngine→MergeEngine→합성 EnrichCutoffProfile 까지 통과하는지 검증.
임베딩은 stub (InMemoryVectorIndex) — 네트워크/벡터DB 불요.
"""
from __future__ import annotations

import pytest

from domains._shared.adapters.vector_index_memory import InMemoryVectorIndex
from domains._shared.segment_registry.concepts import ConceptRegistry
from domains._shared.segment_registry.registry import (
    SegmentProfileRegistry,
    SegmentRegistry,
)
from domains._shared.segment_registry.resolver import SegmentResolver
from infrastructure._common import utils


@pytest.mark.integration
def test_example_governance_loads() -> None:
    concepts = ConceptRegistry(root=utils.concepts_dir())
    c = concepts.load_latest("holdco_value_trap")
    assert c is not None and c.default_threshold == 0.78

    named = SegmentProfileRegistry(root=utils.segment_profiles_dir())
    pc = named.load_latest("holdco_value_floor")
    assert pc is not None and pc.required_enrichments == ("nav_discount",)
    assert pc.cutoff_rules["type"] == "threshold"

    segs = SegmentRegistry(root=utils.segments_dir())
    seg = segs.load_latest("holdco_value_large")
    assert seg is not None and seg.profile_ref == "holdco_value_floor"


@pytest.mark.integration
def test_example_segment_resolves_end_to_end() -> None:
    segs = SegmentRegistry(root=utils.segments_dir())
    all_segments = segs.load_all_latest()
    concepts = ConceptRegistry(root=utils.concepts_dir())
    named = SegmentProfileRegistry(root=utils.segment_profiles_dir())

    # stub 벡터 인덱스: KR:003550 를 concept 에 가깝게 + 대형주로 seed.
    idx = InMemoryVectorIndex()
    meta = dict(model_id="stub", embedded_at="2026-06-12T00:00:00+09:00")
    idx.upsert_vector(kind="concept", key="holdco_value_trap", vector=[1.0, 0.0], text_hash="c", **meta)
    idx.upsert_vector(kind="ticker", key="KR:003550", vector=[0.99, 0.14], text_hash="a", **meta)
    idx.upsert_scalars("KR:003550", {"market_cap_krw": 5e11})

    resolver = SegmentResolver(
        segments=all_segments,
        known_concepts=frozenset(concepts.list_concepts()),
        vector_index=idx,
        named_profile_for=named.load_latest,
        per_ticker_for=lambda t: None,
        now_iso=lambda: "2026-06-12T00:00:00+09:00",
        embedding_model_id="stub",
    )
    res = resolver.resolve("KR:003550")
    assert res.profile is not None
    assert "holdco_value_large" in res.matched_segment_ids
    assert res.profile.required_enrichments == ("nav_discount",)
    assert res.profile.cutoff_rules["type"] == "threshold"
    assert any("EMBED@" in c for c in res.profile.provenance.citations)


@pytest.mark.integration
def test_example_segment_no_match_returns_none() -> None:
    segs = SegmentRegistry(root=utils.segments_dir())
    concepts = ConceptRegistry(root=utils.concepts_dir())
    named = SegmentProfileRegistry(root=utils.segment_profiles_dir())
    idx = InMemoryVectorIndex()  # 벡터 없음 → semantic UNKNOWN → 비매칭

    resolver = SegmentResolver(
        segments=segs.load_all_latest(),
        known_concepts=frozenset(concepts.list_concepts()),
        vector_index=idx,
        named_profile_for=named.load_latest,
        per_ticker_for=lambda t: None,
        now_iso=lambda: "t",
    )
    res = resolver.resolve("KR:999999")
    assert res.profile is None  # Default No-Action (G11)