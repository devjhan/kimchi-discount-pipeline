"""Signal factory — config ``signals:`` 리스트 → Signal 인스턴스 list.

universe ``sources/factory.py`` 와 동등한 layer. 본 모듈 import 시 4 signal 모듈이
함께 로드되어 ``@register_signal`` decorator 가 SIGNALS dict 를 채운다 —
registration 부작용을 한 곳에 집중. 신규 signal = 본 모듈에 import 1줄 추가.
"""
from __future__ import annotations

from typing import Any, Mapping

# 본 import 들이 @register_signal 부작용을 트리거 — 순서 무관, import 자체가 필수.
from domains.macro.signals import breadth as _breadth  # noqa: F401
from domains.macro.signals import credit_spread as _credit_spread  # noqa: F401
from domains.macro.signals import vix as _vix  # noqa: F401
from domains.macro.signals import yield_curve as _yield_curve  # noqa: F401
from domains.macro.signals.base import Signal
from domains.macro.signals.registry import SIGNALS


def build_signals(cfg: Mapping[str, Any]) -> list[Signal]:
    """``config/regimes.yaml`` 의 ``signals:`` 리스트를 인스턴스 list 로 변환.

    ``signals:`` 미지정 시 등록된 전체 signal (등록 순서) 사용.

    Raises:
        ValueError: 등록 안 된 signal 이름.
    """
    names = cfg.get("signals") or list(SIGNALS.keys())
    out: list[Signal] = []
    for n in names:
        cls = SIGNALS.get(n)
        if cls is None:
            raise ValueError(f"unknown signal: '{n}'. registered: {sorted(SIGNALS)}")
        out.append(cls())
    return out
