"""
불변식 — governance/ 는 선언적 doctrine 만 (D-ARCH-1: governance = 입법부, domains = 행정부).

governance/ 에 실행 가능한 .py 가 0 임을 검증. 정책/계약/원칙은 md·yaml 로 선언하고,
기계적 실행은 domains/·infrastructure/ 에 둔다.
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import pytest  # noqa: E402

import _helpers as h  # noqa: E402


@pytest.mark.arch
def test_governance_has_no_executable_python() -> None:
    """governance/ 에 실행 .py 0 — 실행 코드는 domains/infrastructure 로 (D-ARCH-1)."""
    found = [
        h.rel(p)
        for p in (h.REPO_ROOT / "governance").rglob("*.py")
        if "__pycache__" not in p.parts
    ]
    assert not found, f"governance/ 에 .py 발견 (입법부에 실행 코드 금지): {found}"
