"""Violation log — ``domains/_shared/audit/log.ViolationLog`` 의 thin subclass shim.

``bc_name="screener"`` baked-in + screener ``_boundary`` 경유 audit_dir 해석으로
기존 positional 시그니처 (``ViolationLog(clock)``) 와 conftest monkeypatch seam
(``_boundary.resolve_path``) 을 보존. 기록 위치: ``$AUDIT_DIR/screener-violations/{date}.jsonl``.
"""
from __future__ import annotations

from domains._shared.audit.log import ViolationLog as _SharedViolationLog
from domains._shared.time.clock import AsOfClock
from domains.screener import _boundary

__all__ = ["ViolationLog"]


class ViolationLog(_SharedViolationLog):
    """screener BC 일별 JSONL append-only log (bc_name baked in)."""

    def __init__(self, clock: AsOfClock) -> None:
        super().__init__(
            "screener",
            clock,
            audit_dir=lambda: _boundary.resolve_path("operations_audit"),
        )
