"""GuardViolation — invariant 위반 기록 (BC 공통 값 객체).

screener / universe / policy / macro 가 복붙해 온 동일 frozen dataclass 의 SSoT.
각 bounded context 의 모든 violation 은 본 객체로 표현되어 JSONL append-only
``ViolationLog`` (``_shared/audit/log.py``) 에 기록된다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class GuardViolation:
    """단일 invariant 위반."""

    detected_at: datetime
    severity: str
    rule_name: str
    ticker: str | None
    message: str
    context: dict[str, Any] = field(default_factory=dict)
