"""
불변식 A·B — layer 의존 단방향 (D-ARCH-3 / D-CORE-4).

A: infrastructure/ 는 domains/ 를 import 하지 않는다 (infra→domains 역방향 금지).
B: domains/{bc}/application·domain 은 infrastructure 를 직접 import 하지 않는다 (_boundary 경유).

둘 다 현재 GREEN — 본 테스트는 그 상태를 고정(lock-in)한다.
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import pytest  # noqa: E402

import _helpers as h  # noqa: E402

_INFRA_FILES = list(h.iter_py(h.REPO_ROOT / "infrastructure"))
_APP_DOMAIN_FILES = [
    p
    for bc in h.BC_NAMES
    for layer in ("application", "domain")
    for p in h.iter_py(h.REPO_ROOT / "domains" / bc / layer)
]


@pytest.mark.arch
@pytest.mark.parametrize("path", _INFRA_FILES, ids=h.rel)
def test_infrastructure_never_imports_domains(path: pathlib.Path) -> None:
    """불변식 A: infrastructure/ 가 domains/ 를 import 하면 안 된다 (D-CORE-4)."""
    assert not h.imports_prefix(path, "domains"), (
        f"{h.rel(path)} 가 domains 를 import — infrastructure→domains 역방향 (D-CORE-4 / D-ARCH-3 위반)"
    )


@pytest.mark.arch
@pytest.mark.parametrize("path", _APP_DOMAIN_FILES, ids=h.rel)
def test_application_domain_never_imports_infrastructure(path: pathlib.Path) -> None:
    """불변식 B: application/·domain/ 은 infrastructure 직접 import 금지 (_boundary 경유)."""
    assert not h.imports_prefix(path, "infrastructure"), (
        f"{h.rel(path)} 가 infrastructure 직접 import — _boundary 경유해야 함 (D-ARCH-3)"
    )
