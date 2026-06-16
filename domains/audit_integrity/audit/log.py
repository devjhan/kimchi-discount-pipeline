"""Violation log — ``domains/_shared/audit/log.ViolationLog`` 의 thin subclass shim.

``bc_name="audit_integrity"`` baked-in. 기록 위치: ``$AUDIT_DIR/violations/audit_integrity/{date}.jsonl``.
"""
from __future__ import annotations

from domains._shared.audit.log import ViolationLog as _SharedViolationLog
from domains._shared.time.clock import AsOfClock
from domains.audit_integrity import _boundary

__all__ = ["ViolationLog"]


class ViolationLog(_SharedViolationLog):
    """audit_integrity BC 일별 JSONL append-only log (bc_name baked in)."""

    def __init__(self, clock: AsOfClock) -> None:
        super().__init__(
            "audit_integrity",
            clock,
            audit_dir=lambda: _boundary.resolve_path("operations_audit"),
        )
