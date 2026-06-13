"""segment_registry 도메인 예외 계층.

``profile_registry/errors.py`` 와 동형 — silent pass 금지 (Default No-Action 은
``None`` 반환으로 표현, 손상 데이터 / 규약 위반은 raise). 본 패키지는 bc-independent
shared kernel 이므로 어떤 도메인 예외도 본 계층 하위로 통일한다.
"""
from __future__ import annotations


class SegmentRegistryError(Exception):
    """segment_registry 의 모든 도메인 예외의 base."""


class SegmentSchemaError(SegmentRegistryError):
    """SegmentDefinition 스키마 shape 위반 (필수 필드 누락 / 타입 / schema_version)."""


class SegmentNotFoundError(SegmentRegistryError):
    """존재하지 않는 segment_id / version 의 명시적 조회."""


class ConceptSchemaError(SegmentRegistryError):
    """ConceptDeclaration 스키마 shape 위반."""


class ConceptNotFoundError(SegmentRegistryError):
    """존재하지 않는 concept_id / version 의 명시적 조회."""


class SelectorError(SegmentRegistryError):
    """selector predicate tree 의 문법 위반 (미지원 type / 미등록 attribute·concept / op)."""


class MergeConflictError(SegmentRegistryError):
    """명시적 merge spec 으로 해소되지 않는 충돌 — 암묵 동작 금지 (6-a)."""


class SegmentCycleError(SegmentRegistryError):
    """segment 계층(parent) 에 순환이 존재 — 해소 순서 정의 불가."""
