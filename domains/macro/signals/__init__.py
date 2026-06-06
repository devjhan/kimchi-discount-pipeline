"""macro Signal 플러그인 패키지 — vote-in-signal (fetch + vote 캡슐화).

registration 트리거는 ``factory.py`` (import 시 4 signal 모듈 로드). 소비자는
``from domains.macro.signals.factory import build_signals, SIGNALS`` 또는
registry 직접 접근. 새 indicator = Signal 1 클래스 + factory import 1줄 +
``config/regimes.yaml`` ``signals:`` 한 줄.
"""
from __future__ import annotations

from domains.macro.signals.base import Signal, empty_indicator
from domains.macro.signals.registry import SIGNALS, register_signal

__all__ = ["Signal", "empty_indicator", "SIGNALS", "register_signal"]
