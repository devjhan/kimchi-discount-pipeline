"""policy_profile 도메인 예외.

``PolicyProfileSchemaError`` 는 legacy ``ProfileSchemaError`` + ``SegmentSchemaError``
*양쪽* 을 상속한다 — 통합 serde 가 raise 해도 기존 소비자의 ``except ProfileSchemaError``
(profile_registry / policy) 와 ``except SegmentSchemaError`` / ``SegmentRegistryError``
(segment_registry / screener / universe) 가 모두 잡도록 (ADR-0013 Q2 수렴 호환).
"""
from __future__ import annotations

from domains._shared.profile_registry.errors import ProfileSchemaError
from domains._shared.segment_registry.errors import SegmentSchemaError


class PolicyProfileSchemaError(ProfileSchemaError, SegmentSchemaError):
    """통합 policy-profile 스키마 shape 위반 (scope / 필수 필드 / schema_version)."""
