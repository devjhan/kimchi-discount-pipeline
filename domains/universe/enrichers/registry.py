"""Enricher type registry — ``@register_enricher(name)`` decorator + dict.

sources/registry.py 와 isomorphic 패턴. 중복 등록은 ValueError.
"""
from __future__ import annotations

from typing import Callable, TypeVar

from domains.universe.enrichers.base import Enricher

ENRICHER_TYPES: dict[str, type[Enricher]] = {}

T = TypeVar("T", bound=Enricher)


def register_enricher(name: str) -> Callable[[type[T]], type[T]]:
    """enricher type 등록 decorator. 중복 등록은 ValueError."""

    def deco(cls: type[T]) -> type[T]:
        if name in ENRICHER_TYPES:
            raise ValueError(
                f"enricher type '{name}' already registered: {ENRICHER_TYPES[name].__name__}"
            )
        ENRICHER_TYPES[name] = cls
        return cls

    return deco
