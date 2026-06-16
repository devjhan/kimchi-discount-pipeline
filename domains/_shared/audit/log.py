"""Violation log — append-only JSONL (BC ``bc_name`` 파라미터화, SSoT).

screener / universe / policy / macro 가 복붙해 온 ``ViolationLog`` 의 단일 구현.
BC 간 차이였던 디렉토리 이름을 ``bc_name`` 생성자 인자로 추출했다 (concern 별
subdir 그룹화, ADR-0008 retention class). ``$AUDIT_DIR/violations/{bc_name}/{date}.jsonl``
에 기록.

각 BC 의 ``audit/log.py`` 는 본 클래스를 ``bc_name`` baked-in 한 thin subclass 로
감싸 기존 positional 시그니처 ``ViolationLog(clock)`` 와 그 BC 의 ``_boundary``
경유 audit_dir 해석 (conftest monkeypatch seam) 을 보존한다.

레이어: ``audit_dir`` 미주입 시 ``infrastructure._common.utils.audit_dir()`` 를
lazy import 로 fallback (``$AUDIT_DIR`` env override 존중). vendor adapter import
금지 규약 (``_shared/__init__.py``) 은 유지된다.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable

from domains._shared.audit.violation import GuardViolation
from domains._shared.time.clock import AsOfClock


class ViolationLog:
    """BC 파라미터화 일별 JSONL append-only log.

    Args:
        bc_name: violations subdir 이름 (예: ``"screener"`` → ``violations/screener/``).
        clock: 기록 일자 결정 (``trading_date``).
        audit_dir: ``$AUDIT_DIR`` 해석 override. ``Path`` 또는 ``() -> Path``
            callable (BC ``_boundary.resolve_path("operations_audit")`` 주입용 —
            conftest monkeypatch seam). ``None`` 이면 ``utils.audit_dir()`` fallback.
    """

    def __init__(
        self,
        bc_name: str,
        clock: AsOfClock,
        *,
        audit_dir: Path | Callable[[], Path] | None = None,
    ) -> None:
        self._bc_name = bc_name
        self._clock = clock
        self._audit_dir = audit_dir
        self._has_blocking = False

    @property
    def has_blocking(self) -> bool:
        """severity='blocking' violation 이 1+ 기록되었는지."""
        return self._has_blocking

    def record(self, violation: GuardViolation) -> Path:
        """violation 1건 append. severity='blocking' 이면 has_blocking=True."""
        if violation.severity == "blocking":
            self._has_blocking = True
        log_path = self._log_path()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        record = _to_jsonable(asdict(violation))
        with log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        return log_path

    def _log_path(self) -> Path:
        return (
            self._resolve_audit_dir()
            / "violations"
            / self._bc_name
            / f"{self._clock.trading_date.isoformat()}.jsonl"
        )

    def _resolve_audit_dir(self) -> Path:
        if self._audit_dir is None:
            from infrastructure._common import utils as _utils

            return _utils.audit_dir()
        if callable(self._audit_dir):
            return self._audit_dir()
        return self._audit_dir


def _to_jsonable(obj: Any) -> Any:
    """dataclass.asdict 가 datetime 을 datetime 그대로 남김 — isoformat 변환."""
    if hasattr(obj, "isoformat"):
        return obj.isoformat(timespec="seconds")
    if isinstance(obj, dict):
        return {k: _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_jsonable(v) for v in obj]
    return obj
