"""PolicyProfile — scope-tagged 통합 정책 프로파일 frozen value object (ADR-0013 Q2).

세 tier(global / segment / ticker)가 공통으로 가진 ``required_enrichments + cutoff_rules``
shape 를 단일 dataclass 로 수렴한다. identity 는 ``key`` 로 일반화:

- scope=ticker  → ``key`` = "KR:NNNNNN" (per-ticker 직접조회 identity)
- scope=segment → ``key`` = named profile 이름 (segment 가 profile_ref 로 참조)
- scope=global  → ``key`` = global profile 이름 (예: "quality_floor")

하우스 스타일: frozen dataclass + ``__post_init__`` 수동 검증 (Pydantic 아님). ``Provenance``
는 ``profile_registry`` 의 것을 재사용 — 저장소 전역 단일 Provenance 유지 (신규 의존성 0).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

# Provenance 는 profile_registry 의 단일 정의를 재사용 (순환 없음 — profile_registry.schema
# 는 leaf, 본 모듈을 import 하지 않음). 저장소 전역 동일 Provenance 클래스 유지.
from domains._shared.profile_registry.schema import Provenance
from domains._shared.policy_profile.errors import PolicyProfileSchemaError

SCHEMA_VERSION = "policy-profile-v1"
"""bump => serde.from_dict 가 마이그레이션 게이트로 reject. 호환 깨질 때만 올림."""

VALID_SCOPES = frozenset({"global", "segment", "ticker"})
"""정책 scope — general(global) → specific(ticker) precedence."""

__all__ = ["SCHEMA_VERSION", "VALID_SCOPES", "PolicyProfile", "Provenance"]


@dataclass(frozen=True)
class PolicyProfile:
    """scope-tagged 통합 정책 프로파일. universe(enrich) + screener(cutoff) 가 소비.

    - ``required_enrichments`` — universe enricher name 집합. 빈 tuple 허용.
    - ``cutoff_rules`` — screener Rule dict-tree (``{"type": ...}``). opaque passthrough —
      룰 *의미* 는 RuleFactory 단독 검증. 빈 dict 허용(=cutoff 기여 없음). 단 scope=ticker
      는 비어 있을 수 없음(per-ticker 프로파일은 항상 cutoff 보유 — legacy parity).
    - ``qualitative_lenses`` — LLM 정성 lens 메타 (주로 global). 기본 빈 tuple.
    """

    scope: str
    """global | segment | ticker."""

    key: str
    """scope=ticker: "KR:NNNNNN"; scope∈{segment,global}: 정책 이름."""

    schema_version: str
    """== SCHEMA_VERSION."""

    profile_version: int
    """monotonic 정수 (1, 2, 3, ...)."""

    required_enrichments: tuple[str, ...]
    """universe 가 적용할 enricher name 집합."""

    cutoff_rules: Mapping[str, Any]
    """screener Rule dict-tree (RuleFactory 소비). 비어 있지 않으면 'type' 키 필수."""

    provenance: Provenance
    """commit 근거 + G7 citations. global/segment 는 빈 Provenance 허용."""

    qualitative_lenses: tuple[str, ...] = ()
    """LLM 정성 lens 정의 (stage2-quality-lens). 주로 scope=global."""

    description: str = ""
    """config-header lint(D-CFG-1) 대응 — on-disk YAML 의 description 미러."""

    def __post_init__(self) -> None:
        if self.scope not in VALID_SCOPES:
            raise PolicyProfileSchemaError(
                f"scope 는 {sorted(VALID_SCOPES)} 중 하나: {self.scope!r}"
            )
        if self.schema_version != SCHEMA_VERSION:
            raise PolicyProfileSchemaError(
                f"schema_version mismatch: {self.schema_version!r} "
                f"(expected {SCHEMA_VERSION!r})"
            )
        if self.profile_version < 1:
            raise PolicyProfileSchemaError("profile_version >= 1")
        if not self.key or not self.key.strip():
            raise PolicyProfileSchemaError("key 는 비어 있을 수 없음")
        if self.scope == "ticker" and ":" not in self.key:
            raise PolicyProfileSchemaError(
                f"scope=ticker 의 key 는 'KR:NNNNNN' 형식: {self.key!r}"
            )
        if not isinstance(self.cutoff_rules, Mapping):
            raise PolicyProfileSchemaError("cutoff_rules 는 Mapping 이어야 함")
        if self.cutoff_rules and "type" not in self.cutoff_rules:
            raise PolicyProfileSchemaError(
                "비어 있지 않은 cutoff_rules 는 'type' 키 필요 (Rule dict-tree)"
            )
        if self.scope == "ticker" and not self.cutoff_rules:
            raise PolicyProfileSchemaError(
                "scope=ticker 는 cutoff_rules('type' dict-tree) 필수 (per-ticker parity)"
            )
        # NOTE: 룰 의미(metric_path / op)는 검증하지 않음 — RuleFactory 책임.

    @property
    def has_cutoff(self) -> bool:
        """cutoff_rules 기여 여부 (segment contribution 의 enrichments-only 판별)."""
        return bool(self.cutoff_rules)
