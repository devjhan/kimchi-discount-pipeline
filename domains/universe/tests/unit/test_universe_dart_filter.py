"""DartDisclosureFilter 특성화(characterization) 테스트 — Phase 1 byte-parity 가드.

기존 직접 커버 부재(test_universe_sources 는 literal/holding/preferred 만) → 본 테스트가
``_maybe_build_entry`` / ``discover``(progressive degrade) 의 정확한 산출을 고정한다.
shared ``disclosure_scan`` primitive 이행 전후 동일 통과 = byte-parity 증명.
"""
from __future__ import annotations

from datetime import date

import pytest

from domains._shared.time.clock import AsOfClock
from domains.universe import _boundary
from domains.universe.sources.base import DiscoveryContext
from domains.universe.sources.dart_disclosure_filter import DartDisclosureFilter

FIXED_TS = "2026-05-15T15:30:00+09:00"


def _ctx() -> DiscoveryContext:
    return DiscoveryContext(
        clock=AsOfClock.at_market_close(date(2026, 5, 15)),
        env={"DART_API_KEY": "testkey"},
    )


@pytest.fixture(autouse=True)
def _stub_boundary(monkeypatch: pytest.MonkeyPatch) -> None:
    """dart_has_key / now_iso_kst stub (DART/네트워크 회피)."""
    monkeypatch.setattr(_boundary, "dart_has_key", lambda env: True)
    monkeypatch.setattr(_boundary, "now_iso_kst", lambda: FIXED_TS)


def _treasury_filter(**over: object) -> DartDisclosureFilter:
    kw: dict[str, object] = dict(
        name="treasury_action",
        pblntf_ty="B",
        lookback_months=6,
        keyword_groups={
            "cancellation": ("자기주식소각", "이익소각"),
            "acquisition": ("자기주식취득",),
        },
        source_category="treasury_action",
        progressive_degrade=False,
        priority_groups={"cancellation": "high_priority"},
    )
    kw.update(over)
    return DartDisclosureFilter(**kw)  # type: ignore[arg-type]


def _patch_iter(
    monkeypatch: pytest.MonkeyPatch, items: list[dict], *, fail_first: bool = False
) -> dict[str, int]:
    calls = {"n": 0}

    def fake(api_key, *, bgn_de, end_de, pblntf_ty=None, corp_code=None):  # type: ignore[no-untyped-def]
        calls["n"] += 1
        if fail_first and calls["n"] == 1:
            raise _boundary.DartUnavailable("simulated")
        return list(items)

    monkeypatch.setattr(_boundary, "dart_iter_disclosures", fake)
    return calls


@pytest.mark.unit
def test_basic_match_metadata_citation(monkeypatch: pytest.MonkeyPatch) -> None:
    """단일 매칭 → kind/priority_note metadata + G7 citation + 필드 정확."""
    items = [
        {"report_nm": "자기주식소각 결정", "stock_code": "000001", "corp_name": "소각주", "rcept_no": "R001", "rcept_dt": "20260510"},
    ]
    _patch_iter(monkeypatch, items)
    res = _treasury_filter().discover(_ctx())
    assert len(res.entries) == 1
    e = res.entries[0]
    assert e.ticker == "KR:000001"
    assert e.name == "소각주"
    assert e.source_category == "treasury_action"
    assert e.inclusion_reason == "cancellation (자기주식소각 결정)"
    assert e.fetched_at == FIXED_TS
    assert e.source_citation == "DART@20260510=R001"
    assert e.metadata == {"kind": "cancellation", "priority_note": "high_priority"}
    assert res.degraded is False


@pytest.mark.unit
def test_no_match_and_bad_stock_code_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    """keyword 미매칭 + stock_code 비-6자리 → 제외."""
    items = [
        {"report_nm": "무관 공시", "stock_code": "000001", "rcept_no": "R001", "rcept_dt": "20260510"},
        {"report_nm": "자기주식소각", "stock_code": "00001", "rcept_no": "R002", "rcept_dt": "20260510"},
    ]
    _patch_iter(monkeypatch, items)
    res = _treasury_filter().discover(_ctx())
    assert res.entries == ()


@pytest.mark.unit
def test_dedup_same_ticker_rcept_group(monkeypatch: pytest.MonkeyPatch) -> None:
    """동일 ticker|rcept_no|group → dedup (1 entry)."""
    items = [
        {"report_nm": "자기주식소각", "stock_code": "000001", "corp_name": "x", "rcept_no": "R001", "rcept_dt": "20260510"},
        {"report_nm": "이익소각", "stock_code": "000001", "corp_name": "x", "rcept_no": "R001", "rcept_dt": "20260510"},
    ]
    _patch_iter(monkeypatch, items)
    res = _treasury_filter().discover(_ctx())
    assert len(res.entries) == 1


@pytest.mark.unit
def test_filer_annotation_known_and_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    """annotate_filers → filer_name/known_activist metadata + inclusion_reason 변형."""
    items = [
        {"report_nm": "주식등의대량보유상황보고서", "stock_code": "000005", "corp_name": "표적", "flr_nm": "행동주의펀드A", "rcept_no": "R005", "rcept_dt": "20260512"},
        {"report_nm": "주식등의대량보유상황보고서", "stock_code": "000006", "corp_name": "표적2", "flr_nm": "일반투자자", "rcept_no": "R006", "rcept_dt": "20260512"},
    ]
    _patch_iter(monkeypatch, items)
    f = DartDisclosureFilter(
        name="activist_filing",
        pblntf_ty="D",
        lookback_months=1,
        keyword_groups={"activist_5pct": ("주식등의대량보유상황",)},
        source_category="activist_filing",
        progressive_degrade=False,
        annotate_filers=("행동주의펀드A", "행동주의펀드B"),
    )
    res = f.discover(_ctx())
    by = {e.ticker: e for e in res.entries}
    known = by["KR:000005"]
    assert known.metadata["known_activist"] is True
    assert known.metadata["filer_name"] == "행동주의펀드A"
    assert known.inclusion_reason == "activist_5pct by 행동주의펀드A [known_activist] (주식등의대량보유상황보고서)"
    unknown = by["KR:000006"]
    assert unknown.metadata["known_activist"] is False
    assert unknown.inclusion_reason == "activist_5pct by 일반투자자 (주식등의대량보유상황보고서)"


@pytest.mark.unit
def test_progressive_degrade_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    """첫 시도 DartUnavailable → 절반 lookback 재시도 성공 → degraded=True + warning."""
    items = [
        {"report_nm": "자기주식소각", "stock_code": "000001", "corp_name": "x", "rcept_no": "R001", "rcept_dt": "20260510"},
    ]
    calls = _patch_iter(monkeypatch, items, fail_first=True)
    res = _treasury_filter(progressive_degrade=True).discover(_ctx())
    assert calls["n"] == 2
    assert res.degraded is True
    assert len(res.entries) == 1
    assert any("progressive degrade succeeded" in w for w in res.warnings)
