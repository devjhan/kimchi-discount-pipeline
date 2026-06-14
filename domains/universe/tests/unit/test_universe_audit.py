"""universe.audit — G7 citation + enricher applies_to invariants + JSONL log."""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from domains._shared.time.clock import AsOfClock
from domains.universe.audit.citation import (
    filter_valid_citations,
    is_valid_citation,
)
from domains.universe.audit.invariants import (
    CitationViolation,
    validate_enricher_applies_to,
    validate_g7_citations,
)
from domains.universe.audit.log import ViolationLog
from domains.universe.audit.violation import GuardViolation
from domains.universe.domain.enriched import EnrichedEntry


# ----------------------------------------------------------------------
# Citation regex
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
    out = filter_valid_citations(cits)
    assert out == ("DART@t=v1", "KIS@t=v2")


# ----------------------------------------------------------------------
# validate_g7_citations
# ----------------------------------------------------------------------


def _entry(
    *,
    ticker: str = "KR:001",
    source_citation: str = "DART@t=v",
    enrichment_citations: tuple[str, ...] = (),
) -> EnrichedEntry:
    return EnrichedEntry(
        ticker=ticker,
        name=ticker,
        source_category="x",
        inclusion_reason="r",
        fetched_at="t",
        source_citation=source_citation,
        enrichment_citations=enrichment_citations,
    )


@pytest.mark.unit
def test_validate_g7_clean_entries_no_violations() -> None:
    entries = [
        _entry(source_citation="DART@t=v1"),
        _entry(source_citation="KIS@t=v2", enrichment_citations=("Yahoo@t=v3",)),
    ]
    assert validate_g7_citations(entries) == []


@pytest.mark.unit
def test_validate_g7_detects_malformed_source_citation() -> None:
    entries = [_entry(ticker="KR:001", source_citation="bad-citation")]
    violations = validate_g7_citations(entries)
    assert len(violations) == 1
    v = violations[0]
    assert isinstance(v, CitationViolation)
    assert v.ticker == "KR:001"
    assert v.bad_citations == ("bad-citation",)


@pytest.mark.unit
def test_validate_g7_detects_malformed_enrichment_citations() -> None:
    entries = [
        _entry(
            ticker="KR:001",
            source_citation="DART@t=v1",  # valid
            enrichment_citations=("KIS@t=v2", "broken", "no_at_sign"),
        )
    ]
    violations = validate_g7_citations(entries)
    assert len(violations) == 1
    assert set(violations[0].bad_citations) == {"broken", "no_at_sign"}


@pytest.mark.unit
def test_validate_g7_ignores_empty_source_citation() -> None:
    """source_citation 이 빈 문자열이면 ignore (manual entries 일부 케이스)."""
    entries = [_entry(source_citation="")]
    assert validate_g7_citations(entries) == []


# ----------------------------------------------------------------------
# validate_enricher_applies_to
# ----------------------------------------------------------------------


@pytest.mark.unit
def test_enricher_applies_to_all_matched_returns_empty() -> None:
    enr_map = {
        "nav": frozenset({"holding_company"}),
        "z": frozenset({"preferred_share_pair"}),
    }
    src_cats = frozenset({"holding_company", "preferred_share_pair", "manual_addition"})
    orphans = validate_enricher_applies_to(enr_map, src_cats)
    assert orphans == []


@pytest.mark.unit
def test_enricher_applies_to_orphan_reported() -> None:
    enr_map = {
        "nav": frozenset({"holding_company"}),
        "ghost": frozenset({"nonexistent_category"}),
    }
    src_cats = frozenset({"holding_company"})
    orphans = validate_enricher_applies_to(enr_map, src_cats)
    assert orphans == ["ghost"]


# ----------------------------------------------------------------------
# ViolationLog JSONL append
# ----------------------------------------------------------------------


KST = timezone(timedelta(hours=9))


@pytest.mark.unit
def test_violation_log_writes_jsonl_and_tracks_blocking(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """ViolationLog.record() — JSONL append + has_blocking 추적."""
    from domains.universe import _boundary

    # _boundary.resolve_path("operations_audit") 를 tmp_path 로 redirect
    monkeypatch.setattr(_boundary, "resolve_path", lambda alias, **kw: tmp_path)

    clock = AsOfClock.at_market_close(date(2026, 5, 17))
    log = ViolationLog(clock)
    assert log.has_blocking is False

    log.record(
        GuardViolation(
            detected_at=datetime(2026, 5, 17, 15, 30, tzinfo=KST),
            severity="warning",
            rule_name="g7_citation_format",
            ticker="KR:001",
            message="bad citation",
            context={"k": "v"},
        )
    )
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

    # JSONL 2 entries
    log_path = tmp_path / "universe-violations" / "2026-05-17.jsonl"
    assert log_path.exists()
    lines = log_path.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 2
    first = json.loads(lines[0])
    assert first["severity"] == "warning"
    assert first["rule_name"] == "g7_citation_format"
    assert first["ticker"] == "KR:001"
    assert first["context"] == {"k": "v"}
    # datetime isoformat 변환
    assert first["detected_at"].startswith("2026-05-17T15:30:00")
