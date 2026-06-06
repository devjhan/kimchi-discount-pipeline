"""Source type registry — ``@register_source(name)`` decorator + dict.

screener 의 ``rules/methods.py`` 패턴과 동등. 중복 등록은 ValueError (silent
override 금지 — silent override 는 conflict drift 의 주된 원인).

신규 source 추가 절차 (Run 2 이후):
1. ``sources/{name}.py`` 에 ``@register_source("{type_name}")`` decorator 가
   부착된 ``@dataclass(frozen=True)`` 클래스 정의 (DiscoverySource ABC 상속)
2. ``sources/factory.py`` 가 본 모듈을 import — 이때 decorator 가 SOURCE_TYPES
   dict 에 등록
3. ``config/sources.yaml`` 에 ``type: {type_name}`` entry 추가
"""
from __future__ import annotations

from typing import Callable, TypeVar

from domains.universe.sources.base import DiscoverySource

SOURCE_TYPES: dict[str, type[DiscoverySource]] = {}

T = TypeVar("T", bound=DiscoverySource)


def register_source(name: str) -> Callable[[type[T]], type[T]]:
    """source type 등록 decorator. 중복 등록은 ValueError."""

    def deco(cls: type[T]) -> type[T]:
        if name in SOURCE_TYPES:
            raise ValueError(
                f"source type '{name}' already registered: {SOURCE_TYPES[name].__name__}"
            )
        SOURCE_TYPES[name] = cls
        return cls

    return deco
