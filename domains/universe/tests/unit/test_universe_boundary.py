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


@pytest.mark.unit
def test_ticker_text_source_none_without_dart_key() -> None:
    """DART 키 부재 → None (build 는 수기 source 만, graceful)."""
    from domains.universe import _boundary

    assert _boundary.ticker_text_source({}) is None


@pytest.mark.unit
def test_ticker_text_source_prefers_mda_then_business_fallback(monkeypatch) -> None:
    """Task 6: ticker_text_source 의 fetch 는 MD&A 1차, 부재 시 사업의 내용 fallback.

    네트워크 0 — corp_index 로드 + 두 fetch 를 stub. MD&A 성공 종목은 MD&A 텍스트,
    MD&A 가 DartUnavailable 인 종목은 사업의 내용 텍스트를 반환해야 한다.
    """
    from domains.universe import _boundary

    monkeypatch.setattr(
        _boundary._dart,
        "load_or_fetch_corp_code_index",
        lambda *a, **k: {"003550": "00120021", "000270": "00106641"},
    )

    def _fake_mda(api_key, *, corp_code, bgn_de, end_de, **kw):
        if corp_code == "00120021":
            return "MD&A 경영진단 본문 (지주)"
        raise _boundary._dart.DartUnavailable("MD&A 부재")

    def _fake_business(api_key, *, corp_code, bgn_de, end_de, **kw):
        return "사업의 내용 본문 (fallback)"

    monkeypatch.setattr(_boundary._dart, "fetch_mda", _fake_mda)
    monkeypatch.setattr(_boundary._dart, "fetch_business_content", _fake_business)

    src = _boundary.ticker_text_source({"DART_API_KEY": "x"})
    assert src is not None
    # MD&A 성공 → MD&A 텍스트.
    assert "MD&A 경영진단 본문" in src.text_for("KR:003550")
    # MD&A DartUnavailable → 사업의 내용 fallback.
    assert "사업의 내용 본문" in src.text_for("KR:000270")


@pytest.mark.unit
def test_ticker_text_source_graceful_when_both_fail(monkeypatch) -> None:
    """MD&A·사업의 내용 둘 다 실패 → '' (DartTickerTextSource 가 raise 안 함, G8)."""
    from domains.universe import _boundary

    monkeypatch.setattr(
        _boundary._dart,
        "load_or_fetch_corp_code_index",
        lambda *a, **k: {"999999": "00000000"},
    )

    def _boom(api_key, *, corp_code, bgn_de, end_de, **kw):
        raise _boundary._dart.DartUnavailable("보고서 부재")

    monkeypatch.setattr(_boundary._dart, "fetch_mda", _boom)
    monkeypatch.setattr(_boundary._dart, "fetch_business_content", _boom)

    src = _boundary.ticker_text_source({"DART_API_KEY": "x"})
    assert src is not None
    assert src.text_for("KR:999999") == ""


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
