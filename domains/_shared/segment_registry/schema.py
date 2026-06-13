"""SegmentDefinition / MergeSpec / PolicyContribution — segment 계층의 frozen 계약.

selector-only (1-b): segment 은 *부분집합을 가르는 selector* + *참조할 정책 이름
(profile_ref)* + *명시적 merge_spec* (6-a) 을 묶는다. 멤버십(selector)과 정책
(profile_ref 가 가리키는 PolicyContribution)은 분리된다.

- ``SegmentDefinition`` — segment 1개의 선언 (parent 로 계층 구성).
- ``MergeSpec`` — 필드별 merge 연산자 (required_enrichments: union|replace,
  cutoff_rules: and|or|replace). 암묵 동작 금지 — 기본값도 명시.
- ``PolicyContribution`` — required_enrichments + cutoff_rules 조각. segment 가 참조하는
  named profile, per-ticker EnrichCutoffProfile, whole-universe default 이 공통으로
  이 형태로 환원되어 MergeEngine 입력이 된다.

본 모듈은 shape 만 검증한다. selector 의미는 SelectorEngine, cutoff_rules 의미는
screener RuleFactory (소비처) 가 단독 검증 — bc-independence 유지.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from domains._shared.profile_registry.schema import Provenance
from domains._shared.segment_registry.errors import SegmentSchemaError

SEGMENT_SCHEMA_VERSION = "segment-def-v1"
# ADR-0013 Q2: named PolicyContribution(=segment scope 정책)의 on-disk 스키마는 통합
# ``policy-profile-v1`` 로 수렴 — PolicyContribution 은 그 scope=segment view (serde 위임).
NAMED_PROFILE_SCHEMA_VERSION = "policy-profile-v1"

REQUIRED_ENRICHMENTS_OPS = frozenset({"union", "replace"})
CUTOFF_RULES_OPS = frozenset({"and", "or", "replace"})


@dataclass(frozen=True)
class MergeSpec:
    """필드별 merge 연산자 (6-a). 기본값도 명시적 — 암묵 동작 없음."""

    required_enrichments: str = "union"
    cutoff_rules: str = "and"

    def __post_init__(self) -> None:
        if self.required_enrichments not in REQUIRED_ENRICHMENTS_OPS:
            raise SegmentSchemaError(
                f"required_enrichments op: {self.required_enrichments!r} "
                f"(허용 {sorted(REQUIRED_ENRICHMENTS_OPS)})"
            )
        if self.cutoff_rules not in CUTOFF_RULES_OPS:
            raise SegmentSchemaError(
                f"cutoff_rules op: {self.cutoff_rules!r} (허용 {sorted(CUTOFF_RULES_OPS)})"
            )


@dataclass(frozen=True)
class PolicyContribution:
    """merge 입력 단위 — required_enrichments + cutoff_rules 조각.

    cutoff_rules 가 빈 dict 이면 "cutoff 기여 없음" (enrichments 만 기여). 비어 있지
    않으면 'type' 키 보유 필수 (Rule dict-tree).
    """

    required_enrichments: tuple[str, ...] = ()
    cutoff_rules: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.cutoff_rules and "type" not in self.cutoff_rules:
            raise SegmentSchemaError(
                "비어 있지 않은 cutoff_rules 는 'type' 키 필요 (Rule dict-tree)"
            )

    @property
    def has_cutoff(self) -> bool:
        return bool(self.cutoff_rules)


@dataclass(frozen=True)
class SegmentDefinition:
    """단일 segment 선언. parent 로 계층, selector 로 멤버십, profile_ref 로 정책 참조."""

    segment_id: str
    schema_version: str
    segment_version: int
    selector: Mapping[str, Any]
    profile_ref: str
    merge_spec: MergeSpec
    parent: str | None = None
    priority: int = 0
    provenance: Provenance = field(
        default_factory=lambda: Provenance(committed_at="", committed_by="", trigger="")
    )
    description: str = ""

    def __post_init__(self) -> None:
        if not self.segment_id or not self.segment_id.strip():
            raise SegmentSchemaError("segment_id 는 비어 있을 수 없음")
        if self.schema_version != SEGMENT_SCHEMA_VERSION:
            raise SegmentSchemaError(
                f"schema_version mismatch: {self.schema_version!r} "
                f"(expected {SEGMENT_SCHEMA_VERSION!r})"
            )
        if self.segment_version < 1:
            raise SegmentSchemaError("segment_version >= 1")
        if not isinstance(self.selector, Mapping) or "type" not in self.selector:
            raise SegmentSchemaError("selector 는 'type' 키를 가진 Mapping 이어야 함")
        if not self.profile_ref or not self.profile_ref.strip():
            raise SegmentSchemaError("profile_ref 는 비어 있을 수 없음 (selector-only, 1-b)")
        if self.parent is not None and self.parent == self.segment_id:
            raise SegmentSchemaError(f"segment {self.segment_id!r} 가 자기 자신을 parent 로 지정")
        if not isinstance(self.merge_spec, MergeSpec):
            raise SegmentSchemaError("merge_spec 은 MergeSpec 인스턴스여야 함")
