"""GuardViolation — ``domains/_shared/audit/violation`` 재export (back-compat).

screener bounded context 의 violation 값 객체는 공유 커널 SSoT 를 사용한다.
기존 import 경로 (``from domains.screener.audit.violation import GuardViolation``)
보존을 위한 thin re-export.
"""
from __future__ import annotations

from domains._shared.audit.violation import GuardViolation

__all__ = ["GuardViolation"]
