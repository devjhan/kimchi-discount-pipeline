"""Detector factory — YAML spec → CatalystDetector 인스턴스.

universe ``sources/factory.py`` 와 동등. 본 모듈 import 시 모든 detector 모듈이
함께 로드되어 ``@register_detector`` decorator 가 DETECTOR_TYPES 를 채운다.

신규 detector 추가 시 본 모듈에 import 1줄 추가 (그 외 코드 변경 없음).
"""
from __future__ import annotations

from typing import Any

# 본 import 들이 @register_detector 부작용을 트리거한다 — 순서 무관, import 자체는 필수.
from domains.catalyst.detectors import activist_5pct as _activist_5pct  # noqa: F401
from domains.catalyst.detectors import earnings_panic as _earnings_panic  # noqa: F401
from domains.catalyst.detectors import index_deletion as _index_deletion  # noqa: F401
from domains.catalyst.detectors import (  # noqa: F401
    nav_discount_narrowing as _nav_discount_narrowing,
)
from domains.catalyst.detectors import spin_off_merger as _spin_off_merger  # noqa: F401
from domains.catalyst.detectors import (  # noqa: F401
    treasury_cancellation as _treasury_cancellation,
)
from domains.catalyst.detectors.base import CatalystDetector
from domains.catalyst.detectors.registry import DETECTOR_TYPES


def build_detector(spec: dict[str, Any]) -> CatalystDetector:
    """``config/detectors.yaml`` 의 단일 detector spec 을 인스턴스로 변환.

    ``spec`` 은 최소 ``type`` + ``name`` 키 필수.

    Raises:
        ValueError: ``type`` 누락 / 등록 안 된 type / detector 자체 검증 실패
    """
    if not isinstance(spec, dict):
        raise ValueError(f"detector spec 은 dict 이어야 함 (got: {type(spec).__name__})")
    if "type" not in spec:
        raise ValueError(f"detector spec missing 'type' field: {spec}")
    if "name" not in spec:
        raise ValueError(f"detector spec missing 'name' field: {spec}")
    type_name = spec["type"]
    cls = DETECTOR_TYPES.get(type_name)
    if cls is None:
        raise ValueError(
            f"unknown detector type: '{type_name}'. registered: {sorted(DETECTOR_TYPES)}"
        )
    return cls.from_spec(spec)


def build_detectors(specs: list[dict[str, Any]]) -> list[CatalystDetector]:
    """``detectors.yaml`` 의 ``detectors:`` list 전체를 인스턴스 list 로 변환.

    ``enabled: false`` spec 은 인스턴스화는 하되 호출 측(application)에서 skip —
    여기서는 전부 build 하여 ``enabled`` 플래그를 보존한다.
    """
    return [build_detector(s) for s in specs]
