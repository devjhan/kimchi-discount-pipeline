"""dict ↔ SegmentDefinition / PolicyContribution 직렬화.

on-disk YAML 헤더 컨벤션(``schema`` / ``version`` / ``description`` top-level)은
profile_registry serde 와 동일 (D-CFG-1). ``from_*`` 는 schema 게이트.
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Any, Mapping

from domains._shared.policy_profile import serde as _policy_serde
from domains._shared.policy_profile.schema import (
    SCHEMA_VERSION as _POLICY_SCHEMA_VERSION,
)
from domains._shared.policy_profile.schema import PolicyProfile
from domains._shared.profile_registry.schema import Provenance
from domains._shared.segment_registry.errors import SegmentSchemaError
from domains._shared.segment_registry.schema import (
    SEGMENT_SCHEMA_VERSION,
    MergeSpec,
    PolicyContribution,
    SegmentDefinition,
)


def _provenance_from(raw: Mapping[str, Any]) -> Provenance:
    prov = raw or {}
    return Provenance(
        committed_at=prov.get("committed_at", ""),
        committed_by=prov.get("committed_by", ""),
        trigger=prov.get("trigger", ""),
        citations=tuple(prov.get("citations") or ()),
        rationale_ko=prov.get("rationale_ko", ""),
    )


def _provenance_dict(p: Provenance) -> dict[str, Any]:
    return {**asdict(p), "citations": list(p.citations)}


# ----------------------------------------------------------------------
# SegmentDefinition
# ----------------------------------------------------------------------
def segment_to_dict(s: SegmentDefinition) -> dict[str, Any]:
    return {
        "schema": s.schema_version,
        "version": s.segment_version,
        "description": s.description,
        "segment_id": s.segment_id,
        "parent": s.parent,
        "priority": s.priority,
        "profile_ref": s.profile_ref,
        "selector": dict(s.selector),
        "merge": {
            "required_enrichments": s.merge_spec.required_enrichments,
            "cutoff_rules": s.merge_spec.cutoff_rules,
        },
        "provenance": _provenance_dict(s.provenance),
    }


def segment_from_dict(raw: Mapping[str, Any]) -> SegmentDefinition:
    sv = raw.get("schema")
    if sv != SEGMENT_SCHEMA_VERSION:
        raise SegmentSchemaError(
            f"unsupported schema: {sv!r} (expected {SEGMENT_SCHEMA_VERSION!r})"
        )
    merge_raw = raw.get("merge") or {}
    try:
        merge = MergeSpec(
            required_enrichments=merge_raw.get("required_enrichments", "union"),
            cutoff_rules=merge_raw.get("cutoff_rules", "and"),
        )
        return SegmentDefinition(
            segment_id=raw["segment_id"],
            schema_version=sv,
            segment_version=int(raw["version"]),
            selector=raw["selector"],
            profile_ref=raw["profile_ref"],
            merge_spec=merge,
            parent=raw.get("parent"),
            priority=int(raw.get("priority", 0)),
            provenance=_provenance_from(raw.get("provenance") or {}),
            description=raw.get("description", ""),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise SegmentSchemaError(f"segment dict 파싱 실패: {exc}") from exc


# ----------------------------------------------------------------------
# Named PolicyContribution (segment 가 profile_ref 로 참조)
# ----------------------------------------------------------------------
def named_profile_to_dict(
    name: str, version: int, contribution: PolicyContribution, *, description: str = ""
) -> dict[str, Any]:
    """named PolicyContribution → on-disk dict (통합 policy-profile-v1, scope=segment).

    ADR-0013 Q2: on-disk 직렬화는 ``policy_profile.serde`` 단일 권위에 위임. PolicyContribution
    은 cutoff_rules + required_enrichments 만 가진 merge-slice view 이므로, name/version/
    description 메타를 합쳐 PolicyProfile(scope=segment)로 투영해 직렬화한다.
    """
    pp = PolicyProfile(
        scope="segment",
        key=name,
        schema_version=_POLICY_SCHEMA_VERSION,
        profile_version=version,
        required_enrichments=contribution.required_enrichments,
        cutoff_rules=contribution.cutoff_rules,
        provenance=Provenance(committed_at="", committed_by="", trigger=""),
        description=description,
    )
    return _policy_serde.to_dict(pp)


def named_profile_from_dict(raw: Mapping[str, Any]) -> PolicyContribution:
    """on-disk dict → PolicyContribution. native(policy-profile-v1) + legacy 모두 수용.

    named profile 은 scope=segment 만 받는다 (다른 scope 파일은 fail-loud). PolicyProfileSchemaError
    는 SegmentSchemaError 의 하위라 기존 except 절이 그대로 잡는다.
    """
    pp = _policy_serde.from_dict(raw)
    if pp.scope != "segment":
        raise SegmentSchemaError(
            f"named profile 은 scope=segment 여야 함 (got {pp.scope!r})"
        )
    return PolicyContribution(
        required_enrichments=pp.required_enrichments,
        cutoff_rules=pp.cutoff_rules,
    )
