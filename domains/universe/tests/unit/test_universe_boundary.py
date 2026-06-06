"""universe 패키지 boundary 검증 — Run 1 scaffold smoke test.

검증 사항:
1. `domains.universe._boundary` 가 import 가능 (빈 stub 도 정상 로드)
2. `UniverseEntry` frozen dataclass 동작 (재할당 거부, equality, 기본 metadata)
3. `domains._shared.time.clock.AsOfClock` 가 screener 에서도 직접 import 가능
   (Run 1.5 에서 screener/time/ 재-export shim 제거 — _shared 가 canonical single source)
4. DDD 경계 grep 검증 — universe 내 `from infrastructure` 는 `_boundary.py` 1 파일만
5. universe 가 다른 도메인 import 금지 (`_shared` 만 예외)
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


@pytest.mark.unit
def test_boundary_module_importable() -> None:
    """빈 stub 상태에서도 boundary 모듈 import 성공."""
    from domains.universe import _boundary  # noqa: F401

    assert hasattr(_boundary, "now_kst")
    assert hasattr(_boundary, "resolve_path")
    assert hasattr(_boundary, "format_citation")
    assert hasattr(_boundary, "load_env")


@pytest.mark.unit
def test_universe_entry_frozen_and_default_metadata() -> None:
    """UniverseEntry 는 frozen — 필드 재할당 시 dataclass.FrozenInstanceError."""
    from dataclasses import FrozenInstanceError

    from domains.universe.domain.entry import UniverseEntry

    entry = UniverseEntry(
        ticker="KR:003550",
        name="(주)LG",
        source_category="holding_company",
        inclusion_reason="기존 universe baseline",
        fetched_at="2026-05-17T15:30:00+09:00",
        source_citation="DART@2026-05-17=baseline",
    )
    assert entry.metadata == {}
    with pytest.raises(FrozenInstanceError):
        entry.ticker = "KR:000000"  # type: ignore[misc]


@pytest.mark.unit
def test_universe_entry_equality_by_value() -> None:
    """frozen dataclass — 동일 필드 값이면 ==."""
    from domains.universe.domain.entry import UniverseEntry

    a = UniverseEntry(
        ticker="KR:003550",
        name="(주)LG",
        source_category="holding_company",
        inclusion_reason="r",
        fetched_at="t",
        source_citation="c",
    )
    b = UniverseEntry(
        ticker="KR:003550",
        name="(주)LG",
        source_category="holding_company",
        inclusion_reason="r",
        fetched_at="t",
        source_citation="c",
    )
    assert a == b


@pytest.mark.unit
def test_screener_time_package_removed() -> None:
    """screener/time/ 디렉토리 제거 — 모든 screener / universe 코드는 _shared 직접 import.

    Run 1.5 정리: 단명한 re-export shim 제거. `from domains.screener.time.clock import
    AsOfClock` 은 더 이상 동작하지 않음 (의도된 변경 — _shared 가 canonical single source).
    """
    import importlib

    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("domains.screener.time.clock")
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("domains.screener.time.calendar")


def _repo_root() -> Path:
    """본 테스트 파일 위치에서 repo root 추론 (tests/unit/test_*.py 기준)."""
    return Path(__file__).resolve().parent.parent.parent


@pytest.mark.unit
def test_boundary_no_infrastructure_import_outside_boundary() -> None:
    """universe 내 `from infrastructure` 는 _boundary.py 1 파일만 허용 (DDD ACL).

    .py 파일만 검사 — .guidelines/*.md 의 예제 코드는 doc 목적이라 무시.
    """
    universe_dir = _repo_root() / "domains" / "universe"
    result = subprocess.run(
        [
            "grep", "-rn", "-E",
            "--include=*.py",
            r"from infrastructure|import infrastructure",
            str(universe_dir),
        ],
        capture_output=True,
        text=True,
    )
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    offenders = [line for line in lines if "/_boundary.py:" not in line]
    assert offenders == [], (
        "universe 내 infrastructure 직접 import 발견 (boundary 우회):\n"
        + "\n".join(offenders)
    )


@pytest.mark.unit
def test_boundary_no_cross_domain_import_except_shared() -> None:
    """universe 가 다른 도메인 import 금지 (_shared 만 예외). .py 파일만 검사."""
    universe_dir = _repo_root() / "domains" / "universe"
    result = subprocess.run(
        [
            "grep", "-rn", "-E",
            "--include=*.py",
            r"from domains\.|import domains\.",
            str(universe_dir),
        ],
        capture_output=True,
        text=True,
    )
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    offenders = []
    for line in lines:
        if "domains.universe" in line:
            continue  # 자기 자신 import 는 정상
        if "domains._shared" in line:
            continue  # _shared 는 예외
        offenders.append(line)
    assert offenders == [], (
        "universe 내 다른 도메인 import 발견:\n" + "\n".join(offenders)
    )
