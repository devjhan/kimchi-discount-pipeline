"""positions_store 도메인 예외 계층.

store / serde 어디서든 raise 되는 예외는 본 계층 하위. silent pass 금지 —
미존재 ticker 는 ``None`` 반환(Default No-Action), 손상 데이터는 raise.
(``profile_registry.errors`` 와 동형.)
"""
from __future__ import annotations


class PositionsStoreError(Exception):
    """positions_store 의 모든 도메인 예외의 base."""


class PositionSchemaError(PositionsStoreError):
    """스키마 shape 위반 (malformed ticker / unknown falsifier category / schema 불일치)."""


class PositionNotFoundError(PositionsStoreError):
    """존재하지 않는 ticker 의 명시적 조회."""
