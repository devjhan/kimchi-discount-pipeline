"""
불변식 — segment_registry 공유 커널의 bc-independence (8-a / 5-a / D-CORE-4).

domains/_shared/segment_registry/ (+ 신규 _shared/adapters) 는:
  - 다른 bounded context (screener/universe/catalyst/...) 를 import 하지 않는다.
  - vendor-specific infra (dart/kis/yahoo/fred/embedding/vectorstore/llm/notify/krx) 를
    직접 import 하지 않는다 — 외부 접촉은 _shared/ports 의 Protocol 주입으로만.
  - infrastructure 는 _common (platform utility) 만 허용.

임베딩/벡터는 EmbeddingPort / VectorIndexPort 로만 접촉해야 함을 고정(lock-in)한다.
"""

from __future__ import annotations

import ast
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import pytest  # noqa: E402

import _helpers as h  # noqa: E402

_KERNEL_DIRS = (
    h.REPO_ROOT / "domains" / "_shared" / "segment_registry",
    h.REPO_ROOT / "domains" / "_shared" / "adapters",
)
_KERNEL_FILES = [p for d in _KERNEL_DIRS for p in h.iter_py(d)]

# 금지: 다른 BC (≠ _shared)
_FORBIDDEN_DOMAIN_PREFIXES = tuple(f"domains.{bc}" for bc in h.BC_NAMES)
# 금지: vendor / 비-_common infra
_FORBIDDEN_INFRA_PREFIXES = (
    "infrastructure.dart",
    "infrastructure.kis",
    "infrastructure.yahoo",
    "infrastructure.fred",
    "infrastructure.krx",
    "infrastructure.llm",
    "infrastructure.notify",
    "infrastructure.embedding",
    "infrastructure.vectorstore",
    "infrastructure.scheduling",
)


def _imported_modules(path: pathlib.Path) -> set[str]:
    """파일이 import 하는 absolute module 전체 경로 (dotted) 집합."""
    mods: set[str] = set()
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                mods.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                mods.add(node.module)
    return mods


@pytest.mark.arch
@pytest.mark.parametrize("path", _KERNEL_FILES, ids=h.rel)
def test_segment_kernel_no_other_domain_import(path: pathlib.Path) -> None:
    mods = _imported_modules(path)
    offenders = [
        m
        for m in mods
        if any(m == p or m.startswith(p + ".") for p in _FORBIDDEN_DOMAIN_PREFIXES)
    ]
    assert not offenders, (
        f"{h.rel(path)} 가 다른 BC 를 import — segment_registry 는 bc-independent 여야 함: {offenders}"
    )


@pytest.mark.arch
@pytest.mark.parametrize("path", _KERNEL_FILES, ids=h.rel)
def test_segment_kernel_no_vendor_infra_import(path: pathlib.Path) -> None:
    mods = _imported_modules(path)
    offenders = [
        m
        for m in mods
        if any(m == p or m.startswith(p + ".") for p in _FORBIDDEN_INFRA_PREFIXES)
    ]
    assert not offenders, (
        f"{h.rel(path)} 가 vendor/비-_common infra 직접 import — "
        f"EmbeddingPort/VectorIndexPort 주입으로만 접촉해야 함: {offenders}"
    )
