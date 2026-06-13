"""dict ↔ EnrichCutoffProfile 직렬화/역직렬화 (ADR-0013 Q2: policy_profile 단일 serde 위임).

on-disk 형식은 통합 ``policy-profile-v1`` (scope=ticker). 본 모듈은 EnrichCutoffProfile
(ticker scope **view**) ↔ ``PolicyProfile`` 투영 + ``policy_profile.serde`` 위임만 한다.
legacy ``enrich-cutoff-profile-v1`` 읽기는 ``policy_profile.serde`` 가 마이그레이션 게이트로
처리한다 (silent pass 금지 — 손상/미지원 schema 는 PolicyProfileSchemaError, 이는
ProfileSchemaError 의 하위라 기존 except 절이 그대로 잡는다).
"""
from __future__ import annotations

from typing import Any, Mapping

from domains._shared.policy_profile import serde as _policy_serde
from domains._shared.policy_profile.schema import (
    SCHEMA_VERSION as _POLICY_SCHEMA_VERSION,
)
from domains._shared.policy_profile.schema import PolicyProfile
from domains._shared.profile_registry.errors import ProfileSchemaError
from domains._shared.profile_registry.schema import SCHEMA_VERSION, EnrichCutoffProfile


def to_dict(p: EnrichCutoffProfile) -> dict[str, Any]:
    """EnrichCutoffProfile(scope=ticker view) → on-disk dict (policy-profile-v1)."""
    pp = PolicyProfile(
        scope="ticker",
        key=p.ticker,
        schema_version=_POLICY_SCHEMA_VERSION,
        profile_version=p.profile_version,
        required_enrichments=p.required_enrichments,
        cutoff_rules=p.cutoff_rules,
        provenance=p.provenance,
        description=p.description,
    )
    return _policy_serde.to_dict(pp)


def from_dict(raw: Mapping[str, Any]) -> EnrichCutoffProfile:
    """on-disk dict → EnrichCutoffProfile. native(policy-profile-v1) + legacy 모두 수용.

    per-ticker 레지스트리는 scope=ticker 만 받는다 (다른 scope 파일은 fail-loud).
    """
    pp = _policy_serde.from_dict(raw)
    if pp.scope != "ticker":
        raise ProfileSchemaError(
            f"per-ticker profile 은 scope=ticker 여야 함 (got {pp.scope!r})"
        )
    return EnrichCutoffProfile(
        ticker=pp.key,
        schema_version=SCHEMA_VERSION,
        profile_version=pp.profile_version,
        required_enrichments=pp.required_enrichments,
        cutoff_rules=pp.cutoff_rules,
        description=pp.description,
        provenance=pp.provenance,
    )
