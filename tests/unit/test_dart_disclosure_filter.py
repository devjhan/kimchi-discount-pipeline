"""DartDisclosureFilter (Run 3) — 3 함수 통합 클래스 단위 테스트.

Pain 1/2 정면 해결의 회귀 방지:
- 3 인스턴스 (treasury / spin_off_or_merger / activist) keyword 매칭 정확성
- progressive degrade retry 가 본 클래스에 single source 로 동작
- annotate_filers / priority_groups 의 metadata 주입
- dedup, fetched_at, source_citation 형식, G8 DART_API_KEY 부재 시 graceful skip
"""
from __future__ import annotations

from datetime import date
from typing import Any, Iterator

import pytest

from domains._shared.time.clock import AsOfClock
from domains.universe import _boundary
from domains.universe.sources.base import DiscoveryContext
from domains.universe.sources.dart_disclosure_filter import DartDisclosureFilter
from domains.universe.sources.factory import build_source


def _ctx(env: dict[str, str] | None = None) -> DiscoveryContext:
    # NOTE: ``env if env is not None else ...`` — ``env or ...`` would treat empty
    # dict as falsy and unexpectedly inject the fallback.
    return DiscoveryContext(
        clock=AsOfClock.at_market_close(date(2026, 5, 17)),
        env=env if env is not None else {"DART_API_KEY": "dummy"},
    )


def _treasury_filter() -> DartDisclosureFilter:
    return DartDisclosureFilter(
        name="treasury_action",
        pblntf_ty="B",
        lookback_months=12,
        keyword_groups={
            "cancellation": ("주식소각", "자기주식소각", "이익소각"),
            "purchase": ("자기주식취득", "자기주식 취득결정"),
        },
        source_category="treasury_action",
        priority_groups={"cancellation": "소각이 본질 catalyst"},
    )


def _spin_off_filter() -> DartDisclosureFilter:
    return DartDisclosureFilter(
        name="spin_off_or_merger",
        pblntf_ty="B",
        lookback_months=24,
        keyword_groups={
            "spin_off": ("분할결정", "회사분할", "인적분할", "물적분할"),
            "merger": ("합병결정", "합병계약", "분할합병결정"),
        },
        source_category="spin_off_or_merger",
    )


def _activist_filter() -> DartDisclosureFilter:
    return DartDisclosureFilter(
        name="activist_filing",
        pblntf_ty="D",
        lookback_months=12,
        keyword_groups={"activist_5pct": ("주식등의대량보유상황",)},
        source_category="activist_filing",
        annotate_filers=("강성부 펀드", "라이프자산운용"),
    )


def _item(
    *,
    stock_code: str = "003550",
    corp_name: str = "(주)LG",
    report_nm: str = "주식소각결정",
    rcept_no: str = "20260501000001",
    rcept_dt: str = "20260501",
    flr_nm: str = "",
) -> dict[str, Any]:
    return {
        "stock_code": stock_code,
        "corp_name": corp_name,
        "report_nm": report_nm,
        "rcept_no": rcept_no,
        "rcept_dt": rcept_dt,
        "flr_nm": flr_nm,
    }


def _mock_iter(items: list[dict[str, Any]]) -> Any:
    """``_boundary.dart_iter_disclosures`` 의 mock — items 그대로 yield."""

    def _impl(api_key: str, **_kwargs: Any) -> Iterator[dict[str, Any]]:
        yield from items

    return _impl


# ----------------------------------------------------------------------
# treasury_action
# ----------------------------------------------------------------------


@pytest.mark.unit
def test_treasury_cancellation_matches_with_priority_note(monkeypatch: pytest.MonkeyPatch) -> None:
    items = [_item(report_nm="자기주식소각결정")]
    monkeypatch.setattr(_boundary, "dart_iter_disclosures", _mock_iter(items))

    result = _treasury_filter().discover(_ctx())
    assert len(result.entries) == 1
    e = result.entries[0]
    assert e.ticker == "KR:003550"
    assert e.source_category == "treasury_action"
    assert e.metadata["kind"] == "cancellation"
    assert e.metadata["priority_note"] == "소각이 본질 catalyst"
    assert "DART@20260501=20260501000001" == e.source_citation
    assert result.degraded is False


@pytest.mark.unit
def test_treasury_purchase_no_priority_note(monkeypatch: pytest.MonkeyPatch) -> None:
    items = [_item(report_nm="자기주식 취득결정")]
    monkeypatch.setattr(_boundary, "dart_iter_disclosures", _mock_iter(items))

    result = _treasury_filter().discover(_ctx())
    assert len(result.entries) == 1
    e = result.entries[0]
    assert e.metadata["kind"] == "purchase"
    assert "priority_note" not in e.metadata


@pytest.mark.unit
def test_treasury_ignores_unmatched_report(monkeypatch: pytest.MonkeyPatch) -> None:
    items = [_item(report_nm="사업보고서")]
    monkeypatch.setattr(_boundary, "dart_iter_disclosures", _mock_iter(items))

    result = _treasury_filter().discover(_ctx())
    assert result.entries == ()


@pytest.mark.unit
def test_treasury_dedup_same_rcept(monkeypatch: pytest.MonkeyPatch) -> None:
    items = [
        _item(report_nm="주식소각결정", rcept_no="X1"),
        _item(report_nm="주식소각결정", rcept_no="X1"),  # 동일 rcept 중복
        _item(report_nm="주식소각결정", rcept_no="X2"),  # 다른 rcept
    ]
    monkeypatch.setattr(_boundary, "dart_iter_disclosures", _mock_iter(items))
    result = _treasury_filter().discover(_ctx())
    assert len(result.entries) == 2


# ----------------------------------------------------------------------
# spin_off_or_merger
# ----------------------------------------------------------------------


@pytest.mark.unit
def test_spin_off_and_merger_share_source_category(monkeypatch: pytest.MonkeyPatch) -> None:
    items = [
        _item(stock_code="003550", report_nm="회사분할결정", rcept_no="A"),
        _item(stock_code="003550", report_nm="합병계약체결", rcept_no="B"),
    ]
    monkeypatch.setattr(_boundary, "dart_iter_disclosures", _mock_iter(items))
    result = _spin_off_filter().discover(_ctx())
    assert len(result.entries) == 2
    categories = {e.source_category for e in result.entries}
    kinds = {e.metadata["kind"] for e in result.entries}
    assert categories == {"spin_off_or_merger"}
    assert kinds == {"spin_off", "merger"}


@pytest.mark.unit
def test_spin_off_first_keyword_group_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    """report_nm 이 spin_off 와 merger 키워드 모두 포함 시 keyword_groups dict
    insertion order 의 첫 매칭 그룹 (spin_off) 사용 — Python 3.7+ dict 순서 보장.

    실제 DART 데이터에서는 이런 dual-match 가 드물지만 deterministic 한 dispatch
    보장이 회귀 방지 차원에서 중요."""
    items = [_item(report_nm="회사분할 및 합병결정 동시 공시", rcept_no="Z")]
    monkeypatch.setattr(_boundary, "dart_iter_disclosures", _mock_iter(items))
    result = _spin_off_filter().discover(_ctx())
    assert len(result.entries) == 1
    assert result.entries[0].metadata["kind"] == "spin_off"


# ----------------------------------------------------------------------
# activist_filing
# ----------------------------------------------------------------------


@pytest.mark.unit
def test_activist_annotate_known_filer(monkeypatch: pytest.MonkeyPatch) -> None:
    items = [
        _item(
            stock_code="000660",
            corp_name="SK하이닉스",
            report_nm="주식등의대량보유상황보고서",
            flr_nm="강성부 펀드 대표 강성부",
        )
    ]
    monkeypatch.setattr(_boundary, "dart_iter_disclosures", _mock_iter(items))
    result = _activist_filter().discover(_ctx())
    assert len(result.entries) == 1
    e = result.entries[0]
    assert e.metadata["filer_name"] == "강성부 펀드 대표 강성부"
    assert e.metadata["known_activist"] is True
    assert "[known_activist]" in e.inclusion_reason


@pytest.mark.unit
def test_activist_unknown_filer(monkeypatch: pytest.MonkeyPatch) -> None:
    items = [_item(report_nm="주식등의대량보유상황보고서", flr_nm="홍길동")]
    monkeypatch.setattr(_boundary, "dart_iter_disclosures", _mock_iter(items))
    result = _activist_filter().discover(_ctx())
    assert len(result.entries) == 1
    e = result.entries[0]
    assert e.metadata["known_activist"] is False
    assert "[known_activist]" not in e.inclusion_reason


# ----------------------------------------------------------------------
# Progressive degrade
# ----------------------------------------------------------------------


@pytest.mark.unit
def test_progressive_degrade_succeeds_on_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    call_count = {"n": 0}

    def _flaky(api_key: str, **_kwargs: Any) -> Iterator[dict[str, Any]]:
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise _boundary.DartUnavailable("transient timeout")
        yield _item(report_nm="주식소각결정", rcept_no="R1")

    monkeypatch.setattr(_boundary, "dart_iter_disclosures", _flaky)
    result = _treasury_filter().discover(_ctx())
    assert call_count["n"] == 2
    assert result.degraded is True
    assert len(result.entries) == 1
    assert any("progressive degrade succeeded" in w for w in result.warnings)


@pytest.mark.unit
def test_progressive_degrade_disabled_no_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    call_count = {"n": 0}

    def _fail(api_key: str, **_kwargs: Any) -> Iterator[dict[str, Any]]:
        call_count["n"] += 1
        raise _boundary.DartUnavailable("hard fail")
        yield  # pragma: no cover

    monkeypatch.setattr(_boundary, "dart_iter_disclosures", _fail)
    src = DartDisclosureFilter(
        name="t",
        pblntf_ty="B",
        lookback_months=12,
        keyword_groups={"x": ("주식소각",)},
        source_category="treasury_action",
        progressive_degrade=False,
    )
    result = src.discover(_ctx())
    assert call_count["n"] == 1  # no retry
    assert result.entries == ()
    assert result.degraded is False
    assert any("all retry attempts failed" in w for w in result.warnings)


@pytest.mark.unit
def test_progressive_degrade_both_attempts_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    call_count = {"n": 0}

    def _fail(api_key: str, **_kwargs: Any) -> Iterator[dict[str, Any]]:
        call_count["n"] += 1
        raise _boundary.DartUnavailable("persistent")
        yield  # pragma: no cover

    monkeypatch.setattr(_boundary, "dart_iter_disclosures", _fail)
    result = _treasury_filter().discover(_ctx())
    assert call_count["n"] == 2  # 12 → 6 retry
    assert result.entries == ()
    assert result.degraded is False
    assert any("all retry attempts failed" in w for w in result.warnings)


# ----------------------------------------------------------------------
# Edge cases
# ----------------------------------------------------------------------


@pytest.mark.unit
def test_skip_when_no_dart_key(monkeypatch: pytest.MonkeyPatch) -> None:
    # iter_disclosures 는 호출되면 안 됨
    monkeypatch.setattr(_boundary, "dart_iter_disclosures", _mock_iter([]))
    result = _treasury_filter().discover(_ctx(env={}))
    assert result.entries == ()
    assert any("DART_API_KEY missing" in w for w in result.warnings)


@pytest.mark.unit
def test_skip_short_stock_code(monkeypatch: pytest.MonkeyPatch) -> None:
    items = [_item(stock_code="123")]  # 3자리 (invalid)
    monkeypatch.setattr(_boundary, "dart_iter_disclosures", _mock_iter(items))
    result = _treasury_filter().discover(_ctx())
    assert result.entries == ()


@pytest.mark.unit
def test_empty_response_no_warnings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_boundary, "dart_iter_disclosures", _mock_iter([]))
    result = _treasury_filter().discover(_ctx())
    assert result.entries == ()
    assert result.warnings == ()


# ----------------------------------------------------------------------
# from_spec / factory integration
# ----------------------------------------------------------------------


@pytest.mark.unit
def test_from_spec_minimal() -> None:
    src = DartDisclosureFilter.from_spec(
        {
            "type": "dart_disclosure_filter",
            "name": "t",
            "pblntf_ty": "B",
            "lookback_months": 12,
            "keyword_groups": {"k": ["주식소각"]},
            "source_category": "treasury_action",
        }
    )
    assert src.name == "t"
    assert src.lookback_months == 12
    assert src.progressive_degrade is True
    assert src.annotate_filers == ()


@pytest.mark.unit
def test_from_spec_rejects_missing_required() -> None:
    base = {
        "type": "dart_disclosure_filter",
        "name": "t",
        "pblntf_ty": "B",
        "lookback_months": 12,
        "keyword_groups": {"k": ["x"]},
        "source_category": "y",
    }
    for missing in ("pblntf_ty", "lookback_months", "keyword_groups", "source_category"):
        spec = {k: v for k, v in base.items() if k != missing}
        with pytest.raises(ValueError, match=missing):
            DartDisclosureFilter.from_spec(spec)


@pytest.mark.unit
def test_from_spec_rejects_empty_keyword_groups() -> None:
    with pytest.raises(ValueError, match="keyword_groups 가 비어 있음"):
        DartDisclosureFilter.from_spec(
            {
                "type": "dart_disclosure_filter",
                "name": "t",
                "pblntf_ty": "B",
                "lookback_months": 12,
                "keyword_groups": {},
                "source_category": "x",
            }
        )


@pytest.mark.unit
def test_factory_dispatches_dart_filter() -> None:
    spec = {
        "type": "dart_disclosure_filter",
        "name": "t",
        "pblntf_ty": "B",
        "lookback_months": 12,
        "keyword_groups": {"k": ["x"]},
        "source_category": "y",
    }
    src = build_source(spec)
    assert isinstance(src, DartDisclosureFilter)


@pytest.mark.unit
def test_sources_yaml_includes_3_dart_filter_instances() -> None:
    """sources.yaml 의 Run 3 추가 entry 검증 — treasury / spin_off_or_merger / activist."""
    cfg = _boundary.load_sources_config()
    dart_specs = [s for s in cfg["sources"] if s["type"] == "dart_disclosure_filter"]
    assert len(dart_specs) == 3
    names = {s["name"] for s in dart_specs}
    assert names == {"treasury_action", "spin_off_or_merger", "activist_filing"}
    # 각 entry build_source 통과
    for s in dart_specs:
        instance = build_source(s)
        assert isinstance(instance, DartDisclosureFilter)
