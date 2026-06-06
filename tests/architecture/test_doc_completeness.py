"""
불변식 — per-BC 문서 표준 + ADR/capability 링크 무결성 (D-ARCH-5 / D-ARCH-6).

- 모든 BC 는 AGENTS.md 를 갖는다 (7/7 GREEN).
- 모든 BC 는 .guidelines/00..05 를 갖는다 (현재 3/7: macro·screener·universe GREEN;
  나머지 4 BC 는 후속 채움 → xfail(strict=False), 채우면 자동 green).
- governance/decisions/ 의 모든 ADR 이 README 인덱스에 링크된다.
- governance/capabilities/ 의 모든 C*.md 가 README 에 링크된다.
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import pytest  # noqa: E402

import _helpers as h  # noqa: E402

# .guidelines/ 미작성 BC (후속 — D-ARCH-5 추적)
_GUIDELINES_DONE: frozenset[str] = frozenset({"macro", "screener", "universe"})
_GUIDELINES_PREFIXES: tuple[str, ...] = ("00", "01", "02", "03", "04", "05")


def _gl_param(bc: str) -> object:
    if bc not in _GUIDELINES_DONE:
        return pytest.param(
            bc,
            marks=pytest.mark.xfail(
                reason=f"{bc}: .guidelines/ 미작성 (후속 작업 — D-ARCH-5 추적). 채우면 자동 green",
                strict=False,
            ),
        )
    return bc


@pytest.mark.arch
@pytest.mark.parametrize("bc", h.BC_NAMES)
def test_bc_has_agents_md(bc: str) -> None:
    """D-ARCH-5: 모든 BC 는 AGENTS.md 를 갖는다 (7/7)."""
    assert (h.REPO_ROOT / "domains" / bc / "AGENTS.md").is_file(), f"{bc}: AGENTS.md 누락"


@pytest.mark.arch
@pytest.mark.parametrize("bc", [_gl_param(b) for b in h.BC_NAMES])
def test_bc_has_guidelines(bc: str) -> None:
    """D-ARCH-5: 모든 BC 는 .guidelines/00..05 를 갖는다 (현재 3/7, 나머지 xfail)."""
    gl = h.REPO_ROOT / "domains" / bc / ".guidelines"
    assert gl.is_dir(), f"{bc}: .guidelines/ 디렉토리 누락"
    prefixes = {f.name[:2] for f in gl.glob("*.md")}
    missing = [n for n in _GUIDELINES_PREFIXES if n not in prefixes]
    assert not missing, f"{bc}: .guidelines 누락 prefix {missing}"


@pytest.mark.arch
def test_adr_index_links_all_files() -> None:
    """D-ARCH-6: governance/decisions/ 의 모든 NNNN-*.md 가 README 인덱스에 링크된다."""
    dec = h.REPO_ROOT / "governance" / "decisions"
    readme = (dec / "README.md").read_text(encoding="utf-8")
    adrs = sorted(p.name for p in dec.glob("[0-9][0-9][0-9][0-9]-*.md"))
    assert adrs, "governance/decisions/ 에 ADR 파일이 없음"
    missing = [a for a in adrs if a not in readme]
    assert not missing, f"ADR README 인덱스 누락 링크: {missing}"


@pytest.mark.arch
def test_capability_files_linked() -> None:
    """capabilities/README 가 모든 C*.md 를 링크한다."""
    cap = h.REPO_ROOT / "governance" / "capabilities"
    readme = (cap / "README.md").read_text(encoding="utf-8")
    files = sorted(p.name for p in cap.glob("C*.md"))
    assert files, "governance/capabilities/ 에 C*.md 가 없음"
    missing = [f for f in files if f not in readme]
    assert not missing, f"capabilities README 누락 링크: {missing}"
