"""dict ↔ EnrichCutoffProfile 직렬화/역직렬화.

on-disk YAML 형식은 하우스 헤더 컨벤션(``schema`` / ``version`` / ``description``)을
top-level 에 둔다 — config-header lint(D-CFG-1) 대응. 내부 dataclass 필드명과
on-disk 키가 다른 부분:
- ``schema`` (on-disk) ↔ ``schema_version`` (dataclass)
- ``version`` (on-disk) ↔ ``profile_version`` (dataclass)

``from_dict`` 은 ``schema`` 게이트 — 미지원 schema_version 은 ProfileSchemaError.
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Any, Mapping

from domains._shared.profile_registry.errors import ProfileSchemaError
from domains._shared.profile_registry.schema import (
    SCHEMA_VERSION,
    EnrichCutoffProfile,
    Provenance,
)


def to_dict(p: EnrichCutoffProfile) -> dict[str, Any]:
    """EnrichCutoffProfile → on-disk dict (YAML dump 직전 형태)."""
    return {
        "schema": p.schema_version,
        "version": p.profile_version,
        "description": p.description,
        "ticker": p.ticker,
        "required_enrichments": list(p.required_enrichments),
        "cutoff_rules": dict(p.cutoff_rules),
        "provenance": {
            **asdict(p.provenance),
            "citations": list(p.provenance.citations),
        },
    }


def from_dict(raw: Mapping[str, Any]) -> EnrichCutoffProfile:
    """on-disk dict → EnrichCutoffProfile. schema 게이트 + KeyError wrap.

    손상 / 누락 필드는 ProfileSchemaError 로 전파 (silent pass 금지).
    """
    sv = raw.get("schema")
    if sv != SCHEMA_VERSION:
        raise ProfileSchemaError(
            f"unsupported schema: {sv!r} (expected {SCHEMA_VERSION!r})"
        )
    prov = raw.get("provenance") or {}
    try:
        return EnrichCutoffProfile(
            ticker=raw["ticker"],
            schema_version=sv,
            profile_version=int(raw["version"]),
            required_enrichments=tuple(raw.get("required_enrichments") or ()),
            cutoff_rules=raw["cutoff_rules"],
            description=raw.get("description", ""),
            provenance=Provenance(
                committed_at=prov.get("committed_at", ""),
                committed_by=prov.get("committed_by", ""),
                trigger=prov.get("trigger", ""),
                citations=tuple(prov.get("citations") or ()),
                rationale_ko=prov.get("rationale_ko", ""),
            ),
        )
    except (KeyError, TypeError, ValueError) as exc:
        # __post_init__ 의 ProfileSchemaError 는 그대로 통과, 그 외는 wrap.
        raise ProfileSchemaError(f"profile dict 파싱 실패: {exc}") from exc
