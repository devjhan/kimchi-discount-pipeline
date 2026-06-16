"""Violation log — ``domains/_shared/audit/log.ViolationLog`` 의 thin subclass shim.

``bc_name="catalyst"`` baked-in + catalyst ``_boundary`` 경유 audit_dir 해석.
기록 위치: ``$AUDIT_DIR/violations/catalyst/{date}.jsonl``.
"""
from __future__ import annotations

from domains._shared.audit.log import ViolationLog as _SharedViolationLog
from domains._shared.time.clock import AsOfClock
from domains.catalyst import _boundary

__all__ = ["ViolationLog"]


class ViolationLog(_SharedViolationLog):
    """catalyst BC 일별 JSONL append-only log (bc_name baked in)."""

    def __init__(self, clock: AsOfClock) -> None:
        super().__init__(
            "catalyst",
            clock,
            audit_dir=lambda: _boundary.resolve_path("operations_audit"),
        )
