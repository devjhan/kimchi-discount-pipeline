"""Signal type registry — ``@register_signal(name)`` decorator + dict.

universe ``sources/registry.py`` · screener ``rules/methods.py`` 패턴과 동등.
중복 등록은 ValueError (silent override 금지 — conflict drift 의 주된 원인).

신규 signal 추가 절차:
1. ``signals/{name}.py`` 에 ``@register_signal("{name}")`` 부착 Signal 서브클래스 정의
2. ``signals/factory.py`` 가 본 모듈을 import — 이때 decorator 가 SIGNALS dict 등록
3. ``config/regimes.yaml`` 의 ``signals:`` 리스트에 ``{name}`` 추가
"""
from __future__ import annotations

from typing import Callable, TypeVar

from domains.macro.signals.base import Signal

SIGNALS: dict[str, type[Signal]] = {}

T = TypeVar("T", bound=Signal)


def register_signal(name: str) -> Callable[[type[T]], type[T]]:
    """signal type 등록 decorator. ``name`` 을 클래스에 부착 + 중복 시 ValueError."""

    def deco(cls: type[T]) -> type[T]:
        if name in SIGNALS:
            raise ValueError(
                f"signal '{name}' already registered: {SIGNALS[name].__name__}"
            )
        cls.name = name
        SIGNALS[name] = cls
        return cls

    return deco
