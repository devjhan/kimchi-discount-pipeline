"""Source factory — YAML spec → DiscoverySource 인스턴스.

screener 의 ``RuleFactory.build_strategy`` 와 동등한 layer. 본 모듈 import 시
모든 source 모듈이 함께 로드되어 ``@register_source`` decorator 가 SOURCE_TYPES
dict 를 채운다 — registration 부작용을 한 곳으로 집중.

신규 source 추가 시 본 모듈에 import 1줄 추가 (그 외 코드 변경 없음).
"""
from __future__ import annotations

from typing import Any

# 본 import 들이 @register_source 부작용을 트리거한다 — 순서 무관, 단 import 자체는 필수.
from domains.universe.sources import dart_disclosure_filter as _dart_disclosure_filter  # noqa: F401
from domains.universe.sources import holding_company as _holding_company  # noqa: F401
from domains.universe.sources import literal_list as _literal_list  # noqa: F401
from domains.universe.sources import preferred_share_pair_seed as _pref_pair_seed  # noqa: F401
from domains.universe.sources.base import DiscoverySource
from domains.universe.sources.registry import SOURCE_TYPES


def build_source(spec: dict[str, Any]) -> DiscoverySource:
    """``config/sources.yaml`` 의 단일 source spec 을 인스턴스로 변환.

    ``spec`` 은 최소 ``type`` + ``name`` 키 필수. 각 source 클래스의 ``from_spec``
    classmethod 가 type-specific 필드 파싱 책임.

    Raises:
        ValueError: ``type`` 누락 / 등록 안 된 type / source 자체 검증 실패
    """
    if not isinstance(spec, dict):
        raise ValueError(f"source spec 은 dict 이어야 함 (got: {type(spec).__name__})")
    if "type" not in spec:
        raise ValueError(f"source spec missing 'type' field: {spec}")
    if "name" not in spec:
        raise ValueError(f"source spec missing 'name' field: {spec}")
    type_name = spec["type"]
    cls = SOURCE_TYPES.get(type_name)
    if cls is None:
        raise ValueError(
            f"unknown source type: '{type_name}'. "
            f"registered: {sorted(SOURCE_TYPES)}"
        )
    return cls.from_spec(spec)


def build_sources(specs: list[dict[str, Any]]) -> list[DiscoverySource]:
    """``sources.yaml`` 의 ``sources:`` list 전체를 인스턴스 list 로 변환."""
    return [build_source(s) for s in specs]
