"""Scoring method registry — value → [0.0, 1.0] 매핑 함수 화이트리스트.

YAML 의 ``method:`` 필드는 본 registry 의 등록된 이름만 허용. 새 method 추가는
본 모듈에 한 줄 추가 + ``python -m applications.gen_methods_manifest`` 재생성
(``governance/policy/methods_manifest.yaml`` 동기, ADR-0014) + unit test 의무.
"""
from __future__ import annotations

import math
from typing import Any, Callable

ScoringFn = Callable[..., float]

SCORING_METHODS: dict[str, ScoringFn] = {}


def register(name: str) -> Callable[[ScoringFn], ScoringFn]:
    """scoring method 등록. 중복 등록은 ValueError."""

    def deco(fn: ScoringFn) -> ScoringFn:
        if name in SCORING_METHODS:
            raise ValueError(f"scoring method '{name}' already registered")
        SCORING_METHODS[name] = fn
        return fn

    return deco


def apply_method(method: str, value: float, **params: Any) -> float:
    """등록된 method 호출. 알 수 없는 method 는 ValueError."""
    fn = SCORING_METHODS.get(method)
    if fn is None:
        raise ValueError(f"unknown scoring method: {method}")
    return fn(value, **params)


@register("piecewise_linear")
def _piecewise_linear(
    value: float,
    *,
    floor: float,
    target: float,
    direction: str = "higher_is_better",
) -> float:
    """[floor, target] 구간 선형 매핑. 바깥은 클립."""
    if direction == "lower_is_better":
        value, floor, target = -value, -floor, -target
    if value <= floor:
        return 0.0
    if value >= target:
        return 1.0
    return (value - floor) / (target - floor)


@register("sigmoid")
def _sigmoid(value: float, *, midpoint: float, steepness: float) -> float:
    """logistic sigmoid — midpoint 중심, steepness 가 기울기."""
    return 1.0 / (1.0 + math.exp(-steepness * (value - midpoint)))


@register("step")
def _step(value: float, *, steps: list[float], scores: list[float]) -> float:
    """value 가 steps[i] 이상이면 scores[i] 적용. steps/scores 길이 동일."""
    if len(steps) != len(scores):
        raise ValueError("steps / scores 길이 불일치")
    result = 0.0
    for s, sc in zip(steps, scores, strict=False):
        if value >= s:
            result = sc
    return result
