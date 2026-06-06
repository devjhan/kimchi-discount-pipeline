"""
tests/architecture/_helpers.py — fitness function 공용 헬퍼.

stdlib (ast / pathlib) 만 사용 — 신규 dependency 0 (D-CORE-5). import-linter 등
외부 도구 미도입. `.claude/hooks/_directive_lint.py` 의 분류 로직과 동형이나, `.claude`
는 패키지가 아니라 import 부적합 → 본 모듈에 자체 포함 (패턴 출처로만 참조). 삭제된
`infrastructure/_common/doctrine_lint.py` 는 참조하지 않는다.

D-ARCH-3/4/5/6 의 repo-wide AST 불변식을 검사하는 4 테스트가 본 모듈을 공유한다.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator
from pathlib import Path

# tests/architecture/_helpers.py → parents[2] = repo root
REPO_ROOT = Path(__file__).resolve().parents[2]

# 실제 bounded context (kernel `_shared` 제외 — _shared 는 설계상 infra 를 wrap 하는 공유 커널)
BC_NAMES: tuple[str, ...] = (
    "macro",
    "universe",
    "screener",
    "catalyst",
    "risk_engine",
    "policy",
    "audit_integrity",
)

# 불변식 C 예외 allowlist — 정당한 최상위 infra-import 스크립트 (composition-root 성격)
BOUNDARY_C_ALLOWLIST: frozenset[str] = frozenset(
    {
        "domains/audit_integrity/init_shadow_state.py",
    }
)

_SKIP_DIRS: frozenset[str] = frozenset(
    {"__pycache__", ".venv", "venv", ".git", "node_modules", ".pytest_cache"}
)


def iter_py(root: Path, *, skip_tests: bool = True) -> Iterator[Path]:
    """root 하위 .py 파일 yield (캐시/가상환경/테스트 디렉토리 제외)."""
    if not root.exists():
        return
    for p in sorted(root.rglob("*.py")):
        parts = set(p.parts)
        if parts & _SKIP_DIRS:
            continue
        if skip_tests and "tests" in p.parts:
            continue
        yield p


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def absolute_import_prefixes(path: Path) -> set[str]:
    """파일이 import 하는 absolute module 의 top-level 이름 집합 (relative import 제외)."""
    mods: set[str] = set()
    for node in ast.walk(_parse(path)):
        if isinstance(node, ast.Import):
            for alias in node.names:
                mods.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                mods.add(node.module.split(".")[0])
    return mods


def imports_prefix(path: Path, prefix: str) -> bool:
    """파일이 `prefix` (top-level package) 를 absolute import 하나."""
    return prefix in absolute_import_prefixes(path)


def imports_boundary(path: Path) -> bool:
    """파일이 `_boundary` 모듈을 import 하나 (absolute 또는 relative 모두 탐지)."""
    for node in ast.walk(_parse(path)):
        if isinstance(node, ast.ImportFrom):
            if node.module and "_boundary" in node.module.split("."):
                return True
            for alias in node.names:
                if alias.name == "_boundary":
                    return True
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if "_boundary" in alias.name.split("."):
                    return True
    return False


def rel(path: Path) -> str:
    """repo root 기준 posix 상대경로 (test id / 에러 메시지용)."""
    return path.relative_to(REPO_ROOT).as_posix()
