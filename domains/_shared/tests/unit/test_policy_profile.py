"""policy_profile — 통합 scope-tagged 정책 프로파일 value object + serde (ADR-0013 Q2).

세 legacy 스키마(enrich-cutoff-profile-v1 / segment-profile-v1 / screener-profile-v1)를
``scope ∈ {global, segment, ticker}`` 단일 ``policy-profile-v1`` 로 수렴. 본 테스트는
TDD 로 작성 — 구현 전 계약을 고정한다.
"""
from __future__ import annotations

import pytest

from domains._shared.policy_profile.errors import PolicyProfileSchemaError
from domains._shared.policy_profile.schema import (
    SCHEMA_VERSION,
    VALID_SCOPES,
    PolicyProfile,
    Provenance,
)
from domains._shared.policy_profile import serde
from domains._shared.profile_registry.errors import ProfileSchemaError
from domains._shared.segment_registry.errors import SegmentSchemaError

pytestmark = pytest.mark.unit


# ----------------------------------------------------------------------
# value object 검증
# ----------------------------------------------------------------------
def test_valid_scopes_exact() -> None:
    assert VALID_SCOPES == frozenset({"global", "segment", "ticker"})


def test_ticker_scope_requires_ticker_format() -> None:
    """scope=ticker 는 key 가 'KR:NNNNNN' 형식 (':' 포함)."""
    with pytest.raises(PolicyProfileSchemaError):
        PolicyProfile(
            scope="ticker",
            key="005930",  # ':' 없음 → reject
            schema_version=SCHEMA_VERSION,
            profile_version=1,
            required_enrichments=(),
            cutoff_rules={"type": "and", "children": []},
            provenance=Provenance(committed_at="", committed_by="", trigger=""),
        )


def test_segment_scope_allows_name_key() -> None:
    """scope=segment 은 name 식별 — ':' 불요."""
    p = PolicyProfile(
        scope="segment",
        key="holdco_value_floor",
        schema_version=SCHEMA_VERSION,
        profile_version=1,
        required_enrichments=("nav_discount",),
        cutoff_rules={},  # segment contribution: enrichments-only 허용
        provenance=Provenance(committed_at="", committed_by="", trigger=""),
    )
    assert p.scope == "segment"
    assert p.has_cutoff is False


def test_invalid_scope_rejected() -> None:
    with pytest.raises(PolicyProfileSchemaError):
        PolicyProfile(
            scope="nonsense",
            key="x",
            schema_version=SCHEMA_VERSION,
            profile_version=1,
            required_enrichments=(),
            cutoff_rules={},
            provenance=Provenance(committed_at="", committed_by="", trigger=""),
        )


def test_nonempty_cutoff_requires_type() -> None:
    with pytest.raises(PolicyProfileSchemaError):
        PolicyProfile(
            scope="global",
            key="quality_floor",
            schema_version=SCHEMA_VERSION,
            profile_version=1,
            required_enrichments=(),
            cutoff_rules={"name": "no_type"},  # 'type' 누락
            provenance=Provenance(committed_at="", committed_by="", trigger=""),
        )


def test_schema_version_mismatch_rejected() -> None:
    with pytest.raises(PolicyProfileSchemaError):
        PolicyProfile(
            scope="global",
            key="quality_floor",
            schema_version="wrong-v9",
            profile_version=1,
            required_enrichments=(),
            cutoff_rules={"type": "and", "children": []},
            provenance=Provenance(committed_at="", committed_by="", trigger=""),
        )


def test_error_is_subclass_of_both_legacy_errors() -> None:
    """PolicyProfileSchemaError 는 ProfileSchemaError + SegmentSchemaError 양쪽 하위 —
    기존 except 절(profile_registry / segment_registry 소비자)이 모두 잡도록."""
    assert issubclass(PolicyProfileSchemaError, ProfileSchemaError)
    assert issubclass(PolicyProfileSchemaError, SegmentSchemaError)


# ----------------------------------------------------------------------
# serde round-trip (native policy-profile-v1)
# ----------------------------------------------------------------------
def test_roundtrip_ticker_scope() -> None:
    p = PolicyProfile(
        scope="ticker",
        key="KR:005930",
        schema_version=SCHEMA_VERSION,
        profile_version=3,
        required_enrichments=("nav_discount", "pref_spread"),
        cutoff_rules={"type": "and", "name": "x", "children": []},
        provenance=Provenance(
            committed_at="2026-06-13T10:00:00+09:00",
            committed_by="policy",
            trigger="filing:rcept_no=1",
            citations=("DART@2026-06-13T10:00:00+09:00=1",),
            rationale_ko="테스트",
        ),
        description="d",
    )
    d = serde.to_dict(p)
    assert d["schema"] == SCHEMA_VERSION
    assert d["scope"] == "ticker"
    assert d["key"] == "KR:005930"
    assert d["version"] == 3
    back = serde.from_dict(d)
    assert back == p


def test_roundtrip_global_with_lenses() -> None:
    p = PolicyProfile(
        scope="global",
        key="quality_floor",
        schema_version=SCHEMA_VERSION,
        profile_version=1,
        required_enrichments=(),
        cutoff_rules={"type": "and", "name": "quality_floor", "children": []},
        provenance=Provenance(committed_at="", committed_by="", trigger=""),
        qualitative_lenses=("moat", "자본배분"),
        description="global quality gate",
    )
    back = serde.from_dict(serde.to_dict(p))
    assert back == p
    assert back.qualitative_lenses == ("moat", "자본배분")


# ----------------------------------------------------------------------
# legacy 스키마 read (마이그레이션 게이트)
# ----------------------------------------------------------------------
def test_read_legacy_enrich_cutoff_v1() -> None:
    legacy = {
        "schema": "enrich-cutoff-profile-v1",
        "version": 2,
        "description": "per-ticker",
        "ticker": "KR:000660",
        "required_enrichments": ["nav_discount"],
        "cutoff_rules": {"type": "and", "children": []},
        "provenance": {
            "committed_at": "2026-06-10T00:00:00+09:00",
            "committed_by": "policy",
            "trigger": "manual",
            "citations": [],
            "rationale_ko": "r",
        },
    }
    p = serde.from_dict(legacy)
    assert p.scope == "ticker"
    assert p.key == "KR:000660"
    assert p.profile_version == 2
    assert p.required_enrichments == ("nav_discount",)
    assert p.provenance.committed_by == "policy"


def test_read_legacy_segment_profile_v1() -> None:
    legacy = {
        "schema": "segment-profile-v1",
        "version": 1,
        "description": "named contribution",
        "name": "holdco_value_floor",
        "required_enrichments": ["nav_discount"],
        "cutoff_rules": {"type": "or", "children": []},
    }
    p = serde.from_dict(legacy)
    assert p.scope == "segment"
    assert p.key == "holdco_value_floor"
    assert p.required_enrichments == ("nav_discount",)
    assert p.cutoff_rules["type"] == "or"


def test_read_legacy_screener_profile_v1_rule_key() -> None:
    """screener-profile-v1 은 rule 트리를 ``rule:`` 키에 둔다 → cutoff_rules 로 매핑 +
    qualitative_lenses 보존."""
    legacy = {
        "schema": "screener-profile-v1",
        "name": "quality_floor",
        "version": 1,
        "description": "quality gate",
        "qualitative_lenses": ["moat", "자본배분"],
        "rule": {"type": "and", "name": "quality_floor", "children": []},
    }
    p = serde.from_dict(legacy)
    assert p.scope == "global"
    assert p.key == "quality_floor"
    assert p.cutoff_rules == {"type": "and", "name": "quality_floor", "children": []}
    assert p.qualitative_lenses == ("moat", "자본배분")


def test_corrupt_dict_fails_loud() -> None:
    with pytest.raises(PolicyProfileSchemaError):
        serde.from_dict({"schema": "policy-profile-v1", "version": 1})  # 필드 누락


def test_unknown_schema_fails_loud() -> None:
    with pytest.raises(PolicyProfileSchemaError):
        serde.from_dict({"schema": "totally-unknown-v1", "version": 1})
