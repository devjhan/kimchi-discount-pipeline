"""Detector type registry — ``@register_detector(name)`` decorator + dict.

universe ``sources/registry.py`` 패턴과 동등. 중복 등록은 ValueError (silent
override 금지).

신규 detector 추가 절차:
1. ``detectors/{name}.py`` 에 ``@register_detector("{type_name}")`` decorator 가
   부착된 ``@dataclass(frozen=True)`` 클래스 정의 (CatalystDetector ABC 상속)
2. ``detectors/factory.py`` 가 본 모듈을 import — decorator 가 DETECTOR_TYPES 등록
3. ``config/detectors.yaml`` 에 ``type: {type_name}`` entry 추가
"""
from __future__ import annotations

from typing import Callable, TypeVar

from domains.catalyst.detectors.base import CatalystDetector

DETECTOR_TYPES: dict[str, type[CatalystDetector]] = {}

T = TypeVar("T", bound=CatalystDetector)


def register_detector(name: str) -> Callable[[type[T]], type[T]]:
    """detector type 등록 decorator. 중복 등록은 ValueError."""

    def deco(cls: type[T]) -> type[T]:
        if name in DETECTOR_TYPES:
            raise ValueError(
                f"detector type '{name}' already registered: {DETECTOR_TYPES[name].__name__}"
            )
        DETECTOR_TYPES[name] = cls
        return cls

    return deco
