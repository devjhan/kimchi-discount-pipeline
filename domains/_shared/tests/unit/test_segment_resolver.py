"""segment_registry.resolver — SegmentResolver 단위 테스트 (Task 7)."""
from __future__ import annotations

import pytest

from domains._shared.adapters.vector_index_memory import InMemoryVectorIndex
from domains._shared.profile_registry.schema import (
    SCHEMA_VERSION as PROFILE_SCHEMA_VERSION,
)
from domains._shared.profile_registry.schema import EnrichCutoffProfile, Provenance
from domains._shared.segment_registry.errors import MergeConflictError
from domains._shared.segment_registry.resolver import SegmentResolver
from domains._shared.segment_registry.schema import (
    SEGMENT_SCHEMA_VERSION,
    MergeSpec,
    PolicyContribution,
    SegmentDefinition,
)

_RULE_HOLDCO = {"type": "threshold", "name": "nav", "metric_path": "x", "op": "ge", "threshold": 0.2}
_RULE_LARGE = {"type": "threshold", "name": "cap", "metric_path": "y", "op": "ge", "threshold": 1}


def _seg(seg_id, selector, profile_ref, *, parent=None, priority=0, merge=None) -> SegmentDefinition:
    return SegmentDefinition(
        segment_id=seg_id,
        schema_version=SEGMENT_SCHEMA_VERSION,
        segment_version=1,
        selector=selector,
        profile_ref=profile_ref,
        merge_spec=merge or MergeSpec(),
        parent=parent,
        priority=priority,
    )


def _index() -> InMemoryVectorIndex:
    idx = InMemoryVectorIndex()
    meta = dict(model_id="m", embedded_at="t")
    idx.upsert_vector(kind="concept", key="holdco", vector=[1.0, 0.0], text_hash="c", **meta)
    idx.upsert_vector(kind="ticker", key="KR:003550", vector=[1.0, 0.0], text_hash="a", **meta)
    idx.upsert_scalars("KR:003550", {"market_cap_krw": 5e11})
    return idx


def _named(mapping):
    return lambda ref: mapping.get(ref)


def _per_ticker(mapping):
    return lambda t: mapping.get(t)


def _resolver(segments, index, *, named=None, per_ticker=None, default=None) -> SegmentResolver:
    return SegmentResolver(
        segments={s.segment_id: s for s in segments},
        known_concepts=frozenset({"holdco"}),
        vector_index=index,
        named_profile_for=_named(named or {}),
        per_ticker_for=_per_ticker(per_ticker or {}),
        default_contribution=default,
        now_iso=lambda: "2026-06-12T00:00:00+09:00",
        embedding_model_id="m",
    )


@pytest.mark.unit
def test_no_match_no_per_ticker_returns_none() -> None:
    seg = _seg(
        "holdco_seg",
        {"type": "semantic_similarity", "concept": "holdco", "op": "ge", "threshold": 0.9},
        "holdco_floor",
    )
    # cosine(KR:003550, holdco)=1.0 ≥ 0.9 → 매칭되지만 profile_ref 미등록 → 기여 없음
    r = _resolver([seg], _index(), named={}).resolve("KR:003550")
    assert r.profile is None
    assert r.matched_segment_ids == ("holdco_seg",)


@pytest.mark.unit
def test_semantic_match_merges_cutoff_and_records_citation() -> None:
    seg = _seg(
        "holdco_seg",
        {"type": "semantic_similarity", "concept": "holdco", "op": "ge", "threshold": 0.9},
        "holdco_floor",
    )
    named = {"holdco_floor": PolicyContribution(("nav_discount",), _RULE_HOLDCO)}
    r = _resolver([seg], _index(), named=named).resolve("KR:003550")
    assert r.profile is not None
    assert r.profile.required_enrichments == ("nav_discount",)
    assert r.profile.cutoff_rules == _RULE_HOLDCO
    assert any(c.startswith("EMBED@") and "holdco" in c for c in r.profile.provenance.citations)
    assert r.profile.provenance.committed_by == "segment-resolver"


@pytest.mark.unit
def test_semantic_unavailable_degrades_to_no_match() -> None:
    # 벡터 미적재 ticker → cosine None → semantic UNKNOWN → 비매칭 (G8/G11)
    seg = _seg(
        "holdco_seg",
        {"type": "semantic_similarity", "concept": "holdco", "op": "ge", "threshold": 0.5},
        "holdco_floor",
    )
    named = {"holdco_floor": PolicyContribution(("nav_discount",), _RULE_HOLDCO)}
    out = _resolver([seg], _index(), named=named).resolve("KR:NOVEC")
    assert out.profile is None
    assert out.matched_segment_ids == ()
    assert any("미가용" in w for w in out.warnings)


@pytest.mark.unit
def test_per_ticker_precedence_union() -> None:
    seg = _seg(
        "large_seg",
        {"type": "threshold", "attribute": "market_cap_krw", "op": "ge", "threshold": 3e11},
        "large_floor",
    )
    named = {"large_floor": PolicyContribution(("spread_zscore",), _RULE_LARGE)}
    per = {
        "KR:003550": EnrichCutoffProfile(
            ticker="KR:003550",
            schema_version=PROFILE_SCHEMA_VERSION,
            profile_version=2,
            required_enrichments=("nav_discount",),
            cutoff_rules=_RULE_HOLDCO,
            provenance=Provenance(committed_at="t", committed_by="policy", trigger="manual"),
        )
    }
    r = _resolver([seg], _index(), named=named, per_ticker=per).resolve("KR:003550")
    assert r.profile is not None
    # union: 둘 다 포함
    assert set(r.profile.required_enrichments) == {"spread_zscore", "nav_discount"}
    # cutoff and-merge: segment 먼저, per-ticker 나중
    assert r.profile.cutoff_rules["type"] == "and"
    assert r.profile.cutoff_rules["children"] == [_RULE_LARGE, _RULE_HOLDCO]


@pytest.mark.unit
def test_default_contribution_base() -> None:
    default = PolicyContribution(("base_enrich",), {})
    r = _resolver([], _index(), default=default).resolve("KR:003550")
    assert r.profile is not None
    assert r.profile.required_enrichments == ("base_enrich",)
    # cutoff 없음 → pass rule
    assert r.profile.cutoff_rules["name"] == "segment_pass"


@pytest.mark.unit
def test_global_default_then_segment_then_per_ticker_precedence() -> None:
    """ADR-0013 decision 4: global(default_contribution) → segment → per-ticker 순서로 fold.

    general(global) 이 가장 먼저, per-ticker(most specific) 가 가장 나중에 AND 된다.
    """
    rule_global = {"type": "threshold", "name": "g", "metric_path": "g", "op": "ge", "threshold": 0.0}
    seg = _seg(
        "large_seg",
        {"type": "threshold", "attribute": "market_cap_krw", "op": "ge", "threshold": 3e11},
        "large_floor",
    )
    named = {"large_floor": PolicyContribution(("spread_zscore",), _RULE_LARGE)}
    per = {
        "KR:003550": EnrichCutoffProfile(
            ticker="KR:003550",
            schema_version=PROFILE_SCHEMA_VERSION,
            profile_version=1,
            required_enrichments=("nav_discount",),
            cutoff_rules=_RULE_HOLDCO,
            provenance=Provenance(committed_at="t", committed_by="policy", trigger="manual"),
        )
    }
    default = PolicyContribution(("g_enrich",), rule_global)
    r = _resolver([seg], _index(), named=named, per_ticker=per, default=default).resolve(
        "KR:003550"
    )
    assert r.profile is not None
    # required_enrichments union 은 세 tier 전부 포함.
    assert set(r.profile.required_enrichments) == {"g_enrich", "spread_zscore", "nav_discount"}
    # cutoff fold 순서: AND(AND(global, segment), per_ticker) — general→specific.
    cutoff = r.profile.cutoff_rules
    assert cutoff["type"] == "and"
    assert cutoff["children"][1] == _RULE_HOLDCO          # per-ticker 가 가장 나중(specific)
    assert cutoff["children"][0]["children"] == [rule_global, _RULE_LARGE]  # global 먼저


@pytest.mark.unit
def test_global_default_only_unmatched_returns_global() -> None:
    """미매칭 + per-ticker 부재 + global default → resolved cutoff == global (screener
    rule_for 가 이를 빌드하면 default_rule 과 동치 — ON-path parity 근거)."""
    rule_global = {"type": "and", "name": "global_q", "children": []}
    default = PolicyContribution((), rule_global)
    r = _resolver([], InMemoryVectorIndex(), default=default).resolve("KR:NOVEC")
    assert r.profile is not None
    assert r.profile.cutoff_rules == rule_global


@pytest.mark.unit
def test_resolve_conflict_raises() -> None:
    s1 = _seg(
        "a",
        {"type": "threshold", "attribute": "market_cap_krw", "op": "ge", "threshold": 1},
        "p",
        priority=1,
    )
    s2 = _seg(
        "b",
        {"type": "threshold", "attribute": "market_cap_krw", "op": "ge", "threshold": 1},
        "p",
        priority=1,
    )
    named = {"p": PolicyContribution(("e",), {})}
    with pytest.raises(MergeConflictError):
        _resolver([s1, s2], _index(), named=named).resolve("KR:003550")
