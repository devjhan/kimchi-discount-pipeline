"""_shared.audit — G7 citation SSoT + bc_name 파라미터화 ViolationLog."""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from domains._shared.audit.citation import (
    CITATION_RE,
    filter_valid_citations,
    is_valid_citation,
)
from domains._shared.audit.log import ViolationLog
from domains._shared.audit.violation import GuardViolation
from domains._shared.time.clock import AsOfClock

KST = timezone(timedelta(hours=9))


# ----------------------------------------------------------------------
# Citation regex (SSoT)
# ----------------------------------------------------------------------


@pytest.mark.unit
def test_citation_regex_accepts_g7_format() -> None:
    assert is_valid_citation("DART@2026-05-17T15:30:00+09:00=20260517000001")
    assert is_valid_citation("KIS@2026-05-17=178.50")
    assert is_valid_citation("user@2026-05-17T15:30:00+09:00=manual_addition")


@pytest.mark.unit
def test_citation_regex_rejects_invalid() -> None:
    assert not is_valid_citation("")
    assert not is_valid_citation("no at sign")
    assert not is_valid_citation("source@ts")  # no =value
    assert not is_valid_citation("@ts=value")  # no source


@pytest.mark.unit
def test_filter_valid_citations_dedup() -> None:
    cits = ("DART@t=v1", "invalid", "KIS@t=v2", "DART@t=v1", "")
    assert filter_valid_citations(cits) == ("DART@t=v1", "KIS@t=v2")


@pytest.mark.unit
def test_bc_shims_share_one_citation_re() -> None:
    """4 BC audit/citation.py 가 동일 SSoT 객체를 재export 하는지 (identity)."""
    from domains.macro.audit.citation import CITATION_RE as macro_re
    from domains.policy.audit.citation import CITATION_RE as policy_re
    from domains.screener.audit.citation import CITATION_RE as screener_re
    from domains.universe.audit.citation import CITATION_RE as universe_re

    assert screener_re is CITATION_RE
    assert universe_re is CITATION_RE
    assert policy_re is CITATION_RE
    assert macro_re is CITATION_RE


# ----------------------------------------------------------------------
# ViolationLog — bc_name 파라미터화
# ----------------------------------------------------------------------


def _violation(severity: str = "warning") -> GuardViolation:
    return GuardViolation(
        detected_at=datetime(2026, 5, 17, 15, 30, tzinfo=KST),
        severity=severity,
        rule_name="g7_citation_format",
        ticker="KR:001",
        message="bad citation",
        context={"k": "v"},
    )


@pytest.mark.unit
def test_violation_log_path_uses_bc_name(tmp_path: Path) -> None:
    """``violations/{bc_name}/{date}.jsonl`` subdir 가 bc_name 으로 결정."""
    clock = AsOfClock.at_market_close(date(2026, 5, 17))
    log = ViolationLog("catalyst", clock, audit_dir=tmp_path)
    log.record(_violation())
    expected = tmp_path / "violations" / "catalyst" / "2026-05-17.jsonl"
    assert expected.exists()


@pytest.mark.unit
def test_violation_log_accepts_callable_audit_dir(tmp_path: Path) -> None:
    """audit_dir 가 callable 이면 record() 시점에 호출 (BC _boundary 주입 seam)."""
    clock = AsOfClock.at_market_close(date(2026, 5, 17))
    log = ViolationLog("screener", clock, audit_dir=lambda: tmp_path)
    log.record(_violation())
    assert (tmp_path / "violations" / "screener" / "2026-05-17.jsonl").exists()


@pytest.mark.unit
def test_violation_log_writes_jsonl_and_tracks_blocking(tmp_path: Path) -> None:
    clock = AsOfClock.at_market_close(date(2026, 5, 17))
    log = ViolationLog("universe", clock, audit_dir=tmp_path)
    assert log.has_blocking is False

    log.record(_violation(severity="warning"))
    assert log.has_blocking is False

    log.record(
        GuardViolation(
            detected_at=datetime(2026, 5, 17, 15, 31, tzinfo=KST),
            severity="blocking",
            rule_name="config_build",
            ticker=None,
            message="boom",
        )
    )
    assert log.has_blocking is True

    log_path = tmp_path / "violations" / "universe" / "2026-05-17.jsonl"
    lines = log_path.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 2
    first = json.loads(lines[0])
    assert first["severity"] == "warning"
    assert first["ticker"] == "KR:001"
    assert first["context"] == {"k": "v"}
    assert first["detected_at"].startswith("2026-05-17T15:30:00")


@pytest.mark.unit
def test_violation_log_default_audit_dir_falls_back_to_utils(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """audit_dir 미주입 시 utils.audit_dir() fallback ($AUDIT_DIR env 존중)."""
    from infrastructure._common import utils as _utils

    monkeypatch.setattr(_utils, "audit_dir", lambda: tmp_path)
    clock = AsOfClock.at_market_close(date(2026, 5, 17))
    log = ViolationLog("macro", clock)  # no audit_dir injected
    log.record(_violation())
    assert (tmp_path / "violations" / "macro" / "2026-05-17.jsonl").exists()
