"""universe --use-segments 배선 (Task 11) — boundary→registries→resolver wiring.

OFF-path parity 는 기존 test_universe_main 전체가 보증(--use-segments 미지정). 본 파일은
ON-path 의 해소기 구성 + required_enrichments 합성을 검증.
"""
from __future__ import annotations

import pytest

from domains._shared.adapters.vector_index_memory import InMemoryVectorIndex
from domains.universe import _boundary
from domains.universe import main as universe_main

pytestmark = pytest.mark.unit


def _seeded_index() -> InMemoryVectorIndex:
    idx = InMemoryVectorIndex()
    meta = dict(model_id="stub", embedded_at="2026-06-12T00:00:00+09:00")
    idx.upsert_vector(kind="concept", key="holdco_value_trap", vector=[1.0, 0.0], text_hash="c", **meta)
    idx.upsert_vector(kind="ticker", key="KR:003550", vector=[0.99, 0.14], text_hash="a", **meta)
    idx.upsert_scalars("KR:003550", {"market_cap_krw": 5e11})
    return idx


def test_segment_resolver_required_enrichments_union(monkeypatch) -> None:
    """매칭 종목 → segment_profile 의 required_enrichments 가 보강된다."""
    idx = _seeded_index()
    monkeypatch.setattr(_boundary, "vector_index", lambda db_path=None: idx)

    resolver = universe_main._build_segment_resolver()
    assert resolver is not None
    res = resolver.resolve("KR:003550")
    assert res.profile is not None
    assert "nav_discount" in res.profile.required_enrichments


def test_segment_resolver_no_match_empty_enrichments(monkeypatch) -> None:
    """벡터 미적재 → 미매칭 → required_enrichments 보강 없음 (Default No-Action)."""
    monkeypatch.setattr(
        _boundary, "vector_index", lambda db_path=None: InMemoryVectorIndex()
    )
    resolver = universe_main._build_segment_resolver()
    assert resolver is not None
    # KR:999999 — segment 미매칭 + per-ticker profile 부재 (KR:003550 은 실 profile 보유, ADR-0014 Phase5).
    res = resolver.resolve("KR:999999")
    assert res.profile is None
