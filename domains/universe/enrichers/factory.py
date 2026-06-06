"""Enricher factory — YAML spec → Enricher 인스턴스.

sources/factory.py 와 isomorphic 패턴. 본 모듈 import 시 모든 enricher 모듈이
함께 로드되어 ``@register_enricher`` decorator 가 ENRICHER_TYPES dict 를 채운다.
"""
from __future__ import annotations

from typing import Any

# 본 import 들이 @register_enricher 부작용을 트리거.
from domains.universe.enrichers import nav_discount as _nav_discount  # noqa: F401
from domains.universe.enrichers import spread_zscore as _spread_zscore  # noqa: F401
from domains.universe.enrichers.base import Enricher
from domains.universe.enrichers.registry import ENRICHER_TYPES


def build_enricher(spec: dict[str, Any]) -> Enricher:
    """``config/enrichers.yaml`` 의 단일 enricher spec 을 인스턴스로 변환."""
    if not isinstance(spec, dict):
        raise ValueError(f"enricher spec 은 dict 이어야 함 (got: {type(spec).__name__})")
    if "type" not in spec:
        raise ValueError(f"enricher spec missing 'type' field: {spec}")
    if "name" not in spec:
        raise ValueError(f"enricher spec missing 'name' field: {spec}")
    type_name = spec["type"]
    cls = ENRICHER_TYPES.get(type_name)
    if cls is None:
        raise ValueError(
            f"unknown enricher type: '{type_name}'. "
            f"registered: {sorted(ENRICHER_TYPES)}"
        )
    return cls.from_spec(spec)


def build_enrichers(specs: list[dict[str, Any]]) -> list[Enricher]:
    """``enrichers.yaml`` 의 ``enrichers:`` list 전체를 인스턴스 list 로 변환."""
    return [build_enricher(s) for s in specs]
