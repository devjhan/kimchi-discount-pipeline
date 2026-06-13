"""dict ↔ PolicyProfile 직렬화 + legacy 3 스키마 read (ADR-0013 Q2 마이그레이션 게이트).

on-disk YAML 헤더 컨벤션(``schema`` / ``version`` / ``description`` top-level)은 저장소
전역 동일 (D-CFG-1). 내부 dataclass 필드명 ↔ on-disk 키:
- ``schema`` (on-disk) ↔ ``schema_version`` (dataclass)
- ``version`` (on-disk) ↔ ``profile_version`` (dataclass)

``from_dict`` 은 ``schema`` 디스패치 게이트:
- ``policy-profile-v1``          → native parse
- ``enrich-cutoff-profile-v1``   → scope=ticker  (legacy per-ticker)
- ``segment-profile-v1``         → scope=segment (legacy named contribution)
- ``screener-profile-v1``        → scope=global  (legacy global; ``rule:`` → cutoff_rules)
- 그 외                          → PolicyProfileSchemaError (silent pass 금지)
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Any, Mapping

from domains._shared.policy_profile.errors import PolicyProfileSchemaError
from domains._shared.policy_profile.schema import (
    SCHEMA_VERSION,
    PolicyProfile,
    Provenance,
)

# legacy on-disk schema 식별자.
_LEGACY_TICKER = "enrich-cutoff-profile-v1"
_LEGACY_SEGMENT = "segment-profile-v1"
_LEGACY_GLOBAL = "screener-profile-v1"


def _provenance_from(raw: Mapping[str, Any] | None) -> Provenance:
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


def to_dict(p: PolicyProfile) -> dict[str, Any]:
    """PolicyProfile → on-disk dict (policy-profile-v1, YAML dump 직전 형태)."""
    out: dict[str, Any] = {
        "schema": p.schema_version,
        "version": p.profile_version,
        "description": p.description,
        "scope": p.scope,
        "key": p.key,
        "required_enrichments": list(p.required_enrichments),
        "cutoff_rules": dict(p.cutoff_rules),
        "provenance": _provenance_dict(p.provenance),
    }
    if p.qualitative_lenses:
        out["qualitative_lenses"] = list(p.qualitative_lenses)
    return out


def from_dict(raw: Mapping[str, Any]) -> PolicyProfile:
    """on-disk dict → PolicyProfile. schema 디스패치 + 손상 필드 fail-loud."""
    sv = raw.get("schema")
    if sv == SCHEMA_VERSION:
        return _from_native(raw)
    if sv == _LEGACY_TICKER:
        return _from_legacy_ticker(raw)
    if sv == _LEGACY_SEGMENT:
        return _from_legacy_segment(raw)
    if sv == _LEGACY_GLOBAL:
        return _from_legacy_global(raw)
    raise PolicyProfileSchemaError(
        f"unsupported schema: {sv!r} (expected {SCHEMA_VERSION!r} 또는 "
        f"legacy {_LEGACY_TICKER!r}/{_LEGACY_SEGMENT!r}/{_LEGACY_GLOBAL!r})"
    )


def _from_native(raw: Mapping[str, Any]) -> PolicyProfile:
    try:
        return PolicyProfile(
            scope=raw["scope"],
            key=raw["key"],
            schema_version=SCHEMA_VERSION,
            profile_version=int(raw["version"]),
            required_enrichments=tuple(raw.get("required_enrichments") or ()),
            cutoff_rules=raw.get("cutoff_rules") or {},
            provenance=_provenance_from(raw.get("provenance")),
            qualitative_lenses=tuple(raw.get("qualitative_lenses") or ()),
            description=raw.get("description", ""),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise PolicyProfileSchemaError(f"policy-profile dict 파싱 실패: {exc}") from exc


def _from_legacy_ticker(raw: Mapping[str, Any]) -> PolicyProfile:
    """legacy enrich-cutoff-profile-v1 → scope=ticker."""
    try:
        return PolicyProfile(
            scope="ticker",
            key=raw["ticker"],
            schema_version=SCHEMA_VERSION,
            profile_version=int(raw["version"]),
            required_enrichments=tuple(raw.get("required_enrichments") or ()),
            cutoff_rules=raw["cutoff_rules"],
            provenance=_provenance_from(raw.get("provenance")),
            description=raw.get("description", ""),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise PolicyProfileSchemaError(f"legacy ticker profile 파싱 실패: {exc}") from exc


def _from_legacy_segment(raw: Mapping[str, Any]) -> PolicyProfile:
    """legacy segment-profile-v1 (named contribution) → scope=segment."""
    try:
        return PolicyProfile(
            scope="segment",
            key=raw["name"],
            schema_version=SCHEMA_VERSION,
            profile_version=int(raw["version"]),
            required_enrichments=tuple(raw.get("required_enrichments") or ()),
            cutoff_rules=raw.get("cutoff_rules") or {},
            provenance=_provenance_from(raw.get("provenance")),
            description=raw.get("description", ""),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise PolicyProfileSchemaError(f"legacy segment profile 파싱 실패: {exc}") from exc


def _from_legacy_global(raw: Mapping[str, Any]) -> PolicyProfile:
    """legacy screener-profile-v1 → scope=global. rule 트리는 ``rule:`` 키에 위치."""
    try:
        return PolicyProfile(
            scope="global",
            key=raw["name"],
            schema_version=SCHEMA_VERSION,
            profile_version=int(raw["version"]),
            required_enrichments=tuple(raw.get("required_enrichments") or ()),
            cutoff_rules=raw["rule"],
            provenance=_provenance_from(raw.get("provenance")),
            qualitative_lenses=tuple(raw.get("qualitative_lenses") or ()),
            description=raw.get("description", ""),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise PolicyProfileSchemaError(f"legacy global profile 파싱 실패: {exc}") from exc
