"""daily_pipeline.sh — external signal 검증 게이트 wiring 스모크 테스트.

게이트 명령이 (1) 존재하고 (2) pre-stage4 마지막(Stage 3 이후, Stage 4 consume·
post-stage4 Stage 5 이전)에 위치하며 (3) 스크립트가 bash 구문상 유효한지 고정한다.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = REPO_ROOT / "applications" / "daily_pipeline.sh"


def _text() -> str:
    return _SCRIPT.read_text(encoding="utf-8")


def test_gate_command_present() -> None:
    assert "domains._shared.external_signal --validate-all" in _text()


def test_gate_runs_before_stage4_consumption() -> None:
    text = _text()
    gate = text.index("run_external_signal_gate()")  # 함수 정의
    gate_call = text.rindex("run_external_signal_gate")  # 호출(마지막 등장)
    after_stage3 = text.index('"Stage 3  — Catalyst Scan"')
    stage5 = text.index('"Stage 5  — Sizing Recommendation"')
    stage4_note = text.index("Stage 5 가 Stage 4 산출 없이")
    # 호출이 Stage 3 이후 & Stage 5(post-stage4)·Stage 4 안내 이전.
    assert after_stage3 < gate_call < stage4_note < stage5
    assert gate < gate_call


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash 미설치")
def test_script_syntax_valid() -> None:
    rc = subprocess.run(
        ["bash", "-n", str(_SCRIPT)],
        capture_output=True,
        text=True,
    )
    assert rc.returncode == 0, rc.stderr
