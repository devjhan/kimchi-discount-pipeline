"""profile_registry 도메인 예외 계층.

registry / serde / commit 어디서든 raise 되는 예외는 본 계층 하위. silent
pass 금지 (Default No-Action 은 ``None`` 반환으로 표현, 손상 데이터는 raise).
"""
from __future__ import annotations


class ProfileRegistryError(Exception):
    """profile_registry 의 모든 도메인 예외의 base."""


class ProfileSchemaError(ProfileRegistryError):
    """스키마 shape 위반 (필수 필드 누락 / 타입 불일치 / schema_version 불일치)."""


class ProfileNotFoundError(ProfileRegistryError):
    """존재하지 않는 ticker / version 의 명시적 조회."""


class ProfileDriftError(ProfileRegistryError):
    """Phase 2 drift gate — threshold 변동이 허용 한계를 초과 (강제 차단 모드)."""
