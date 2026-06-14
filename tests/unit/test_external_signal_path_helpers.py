"""external signal 경로 helper 분리 검증.

per-ticker ingest 증거는 telemetry/external_signals (ADR-0008 분류축 정합),
macro breadth 는 config/signals 잔존 — 두 helper 가 분리됐는지 + env override
seam 이 살아있는지 고정한다.
"""

from __future__ import annotations

import pytest

from infrastructure._common.utils import (
    REPO_ROOT,
    external_signal_intake_dir,
    external_signals_dir,
)


def test_intake_dir_default_is_telemetry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EXTERNAL_SIGNAL_INTAKE_DIR", raising=False)
    assert external_signal_intake_dir() == REPO_ROOT / "telemetry" / "external_signals"


def test_intake_dir_respects_env_override(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("EXTERNAL_SIGNAL_INTAKE_DIR", str(tmp_path / "x"))
    assert external_signal_intake_dir() == tmp_path / "x"


def test_breadth_dir_unchanged_is_config_signals(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """회귀 방지: breadth 용 external_signals_dir 는 여전히 config/signals."""
    monkeypatch.delenv("EXTERNAL_SIGNALS_DIR", raising=False)
    assert external_signals_dir() == REPO_ROOT / "config" / "signals"


def test_two_helpers_are_distinct(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EXTERNAL_SIGNAL_INTAKE_DIR", raising=False)
    monkeypatch.delenv("EXTERNAL_SIGNALS_DIR", raising=False)
    assert external_signal_intake_dir() != external_signals_dir()
