"""
불변식 C·D — _boundary 게이트 (D-ARCH-4 / ADR-0005).

C: BC 당 infrastructure import 은 _boundary.py 만 (+ allowlist). GREEN — hard-assert.
D: application/·domain/ 은 _boundary 를 직접 import 하지 않는다 (composition-root 주입).
   7/7 BC 전환 완료 (2026-06-06) → 전 BC hard-assert. _D_UNCONVERTED 비었음.
   composition root = 각 BC 의 main / 플랫 shim 이 _boundary 를 application 에 주입.
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import pytest  # noqa: E402

import _helpers as h  # noqa: E402

# 불변식 D 미전환 BC — 0/7 (전 BC 전환 완료 2026-06-06: macro/policy/risk_engine 가
# composition-root 주입으로 _boundary 직접 import 제거. ADR-0005 / D-ARCH-4 잔여 해소).
_D_UNCONVERTED: frozenset[str] = frozenset()


def _c_offenders(bc: str) -> list[str]:
    offenders: list[str] = []
    for p in h.iter_py(h.REPO_ROOT / "domains" / bc):
        if p.name == "_boundary.py":
            continue
        if h.rel(p) in h.BOUNDARY_C_ALLOWLIST:
            continue
        if h.imports_prefix(p, "infrastructure"):
            offenders.append(h.rel(p))
    return offenders


def _d_offenders(bc: str) -> list[str]:
    offenders: list[str] = []
    for layer in ("application", "domain"):
        for p in h.iter_py(h.REPO_ROOT / "domains" / bc / layer):
            if h.imports_boundary(p):
                offenders.append(h.rel(p))
    return offenders


def _d_param(bc: str) -> object:
    if bc in _D_UNCONVERTED:
        return pytest.param(
            bc,
            marks=pytest.mark.xfail(
                reason=f"{bc}: _boundary→port 미전환 (ADR-0005 / D-ARCH-4 추적). 전환 시 자동 green",
                strict=False,
            ),
        )
    return bc


@pytest.mark.arch
@pytest.mark.parametrize("bc", h.BC_NAMES)
def test_only_boundary_imports_infrastructure(bc: str) -> None:
    """불변식 C: 각 BC 의 infrastructure import 은 _boundary.py 만 (+ allowlist, D-ARCH-4)."""
    offenders = _c_offenders(bc)
    assert not offenders, f"{bc}: _boundary.py 외 infrastructure import — {offenders}"


@pytest.mark.arch
@pytest.mark.parametrize("bc", [_d_param(b) for b in h.BC_NAMES])
def test_application_domain_does_not_import_boundary(bc: str) -> None:
    """불변식 D: application/·domain/ 은 _boundary 직접 import 안 함 (port 주입 — ADR-0005)."""
    offenders = _d_offenders(bc)
    assert not offenders, f"{bc}: application/domain 이 _boundary 직접 import — {offenders}"
