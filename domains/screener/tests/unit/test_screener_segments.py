"""screener --use-segments 배선 (Task 10) — boundary→registries→resolver wiring.

OFF-path parity 는 기존 test_screener_main / test_screener_resolver 전체가 보증
(--use-segments 미지정). 본 파일은 ON-path 의 해소기 구성 + 예시 governance 합성을 검증.
"""
from __future__ import annotations

import pytest

from domains._shared.adapters.vector_index_memory import InMemoryVectorIndex
from domains._shared.profile_registry.registry import ProfileRegistry
from domains.screener import _boundary
from domains.screener import main as screener_main

pytestmark = pytest.mark.unit


def _seeded_index() -> InMemoryVectorIndex:
    idx = InMemoryVectorIndex()
    meta = dict(model_id="stub", embedded_at="2026-06-12T00:00:00+09:00")
    # KR:003550 → holdco_value_trap concept 에 근접(cosine≈0.99) + 대형주 scalar.
    idx.upsert_vector(kind="concept", key="holdco_value_trap", vector=[1.0, 0.0], text_hash="c", **meta)
    idx.upsert_vector(kind="ticker", key="KR:003550", vector=[0.99, 0.14], text_hash="a", **meta)
    idx.upsert_scalars("KR:003550", {"market_cap_krw": 5e11})
    return idx


def test_build_segment_resolver_wires_example_governance(monkeypatch) -> None:
    """예시 governance(concepts/segments/segment_profiles) + seeded 인덱스 → 매칭·합성."""
    idx = _seeded_index()
    monkeypatch.setattr(_boundary, "vector_index", lambda db_path=None: idx)

    warnings: list[str] = []
    resolver = screener_main._build_segment_resolver(
        ProfileRegistry(root=_boundary.profiles_root()), warnings
    )
    assert resolver is not None
    assert warnings == []

    res = resolver.resolve("KR:003550")
    assert res.profile is not None
    assert "holdco_value_large" in res.matched_segment_ids
    # segment_profile(holdco_value_floor) 의 enrich/cutoff 가 합성됨.
    assert "nav_discount" in res.profile.required_enrichments
    assert res.profile.cutoff_rules
    # semantic 멤버십은 G7 형식 citation 으로 기록.
    assert any("EMBED@" in c for c in res.profile.provenance.citations)


def test_build_segment_resolver_no_match_returns_none(monkeypatch) -> None:
    """벡터 미적재 → semantic UNKNOWN → 미매칭 → profile=None (Default No-Action, G11)."""
    monkeypatch.setattr(
        _boundary, "vector_index", lambda db_path=None: InMemoryVectorIndex()
    )
    warnings: list[str] = []
    resolver = screener_main._build_segment_resolver(
        ProfileRegistry(root=_boundary.profiles_root()), warnings
    )
    assert resolver is not None
    # KR:999999 — segment 미매칭 + per-ticker profile 부재 (KR:003550 은 실 profile 보유, ADR-0014 Phase5).
    res = resolver.resolve("KR:999999")
    assert res.profile is None
    assert res.matched_segment_ids == ()


def test_global_default_contribution_unmatched_byte_parity_with_default_rule(monkeypatch) -> None:
    """ADR-0013 decision 4 ON-path parity: --use-segments 의 global default_contribution 으로
    미매칭 종목이 resolved=global 이 되어도, 빌드된 Rule 트리는 default_rule 과 byte-identical.
    """
    from domains._shared.segment_registry.schema import PolicyContribution
    from domains.screener.rules.factory import RuleFactory

    monkeypatch.setattr(
        _boundary, "vector_index", lambda db_path=None: InMemoryVectorIndex()
    )
    strategy = _boundary.load_strategy("default")
    hard_guards = _boundary.load_hard_guards()
    profile_refs = screener_main._collect_profile_refs(strategy["rule"])
    profiles = {name: _boundary.load_profile(name) for name in profile_refs}
    tax = float((strategy.get("constants") or {}).get("tax_rate", 0.22))

    expanded_global = screener_main._expand_profile_refs(strategy["rule"], profiles)
    default_contribution = PolicyContribution(required_enrichments=(), cutoff_rules=expanded_global)
    resolver = screener_main._build_segment_resolver(
        ProfileRegistry(root=_boundary.profiles_root()),
        [],
        default_contribution=default_contribution,
    )
    assert resolver is not None

    # 미매칭 종목 → resolved profile = global (default_rule 과 동치).
    res = resolver.resolve("KR:NOVEC")
    assert res.profile is not None
    assert res.profile.cutoff_rules == expanded_global

    default_rule = RuleFactory.build_strategy(strategy, profiles, hard_guards, tax_rate=tax)
    resolved_rule = RuleFactory.build_strategy(
        {"name": "segment[KR:NOVEC]", "rule": dict(res.profile.cutoff_rules)},
        {},
        hard_guards,
        tax_rate=tax,
    )
    # outer HardGuardWrapper._name 라벨만 다르고(전략명 vs segment 키), 평가 로직(inner +
    # guards)은 byte-identical — 동일 verdict 보증 (ON-path parity).
    assert resolved_rule.inner == default_rule.inner
    assert resolved_rule.guards == default_rule.guards
