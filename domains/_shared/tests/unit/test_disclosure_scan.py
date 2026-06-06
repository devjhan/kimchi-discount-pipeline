"""domains/_shared/adapters/disclosure_scan — primitive 계약 테스트.

keyword 첫매칭 / stock_code 검증 / keep(dedup 전) / dedup 메커니즘 + DisclosureSourcePort.
universe/catalyst end-to-end byte-parity 는 각 BC 테스트(test_universe_dart_filter /
test_catalyst_golden)가 커버 — 본 테스트는 primitive 자체 계약을 고정한다.
"""
from __future__ import annotations

import pytest

from domains._shared.adapters.disclosure_scan import MatchedDisclosure, scan_disclosures
from domains._shared.ports.disclosure import DisclosureSourcePort


def _src(items: list[dict]):  # type: ignore[no-untyped-def]
    """주입용 DisclosureSourcePort stub — 고정 list 반환."""

    def source(*, bgn_de, end_de, pblntf_ty, corp_code=None):  # type: ignore[no-untyped-def]
        return list(items)

    return source


def _dedup(md: MatchedDisclosure) -> str:
    return f"{md.rcept_no}|{md.matched_group}"


@pytest.mark.unit
def test_keyword_first_match_and_fields() -> None:
    """삽입순 첫매칭 group + MatchedDisclosure 필드 정확."""
    items = [
        {"report_nm": "분할결정 공시", "stock_code": "000002", "rcept_no": "R2", "rcept_dt": "20260511", "corp_name": "분할주"},
    ]
    out = list(
        scan_disclosures(
            _src(items), bgn_de="a", end_de="b", pblntf_ty="B",
            keyword_groups={"spin": ("분할",), "merge": ("합병",)},
            dedup_key=_dedup,
        )
    )
    assert len(out) == 1
    md = out[0]
    assert md.ticker == "KR:000002"
    assert md.matched_group == "spin"
    assert md.rcept_no == "R2"
    assert md.rcept_dt == "20260511"
    assert md.item["corp_name"] == "분할주"


@pytest.mark.unit
def test_stock_code_must_be_6_digits() -> None:
    """stock_code 5자리/빈값 → 제외."""
    items = [
        {"report_nm": "분할", "stock_code": "00002", "rcept_no": "R", "rcept_dt": "d"},
        {"report_nm": "분할", "stock_code": "", "rcept_no": "R", "rcept_dt": "d"},
    ]
    out = list(
        scan_disclosures(
            _src(items), bgn_de="a", end_de="b", pblntf_ty="B",
            keyword_groups={"spin": ("분할",)}, dedup_key=_dedup,
        )
    )
    assert out == []


@pytest.mark.unit
def test_keep_excludes_before_dedup() -> None:
    """keep=False 항목은 제외 (dedup 전 적용)."""
    items = [
        {"report_nm": "분할", "stock_code": "000001", "rcept_no": "R1", "rcept_dt": "d"},
        {"report_nm": "분할", "stock_code": "000002", "rcept_no": "R2", "rcept_dt": "d"},
    ]
    out = list(
        scan_disclosures(
            _src(items), bgn_de="a", end_de="b", pblntf_ty="B",
            keyword_groups={"spin": ("분할",)}, dedup_key=_dedup,
            keep=lambda md: md.ticker == "KR:000002",
        )
    )
    assert [md.ticker for md in out] == ["KR:000002"]


@pytest.mark.unit
def test_dedup_first_wins() -> None:
    """동일 dedup key → 첫 항목만 yield."""
    items = [
        {"report_nm": "분할", "stock_code": "000001", "rcept_no": "R1", "rcept_dt": "d", "corp_name": "first"},
        {"report_nm": "분할", "stock_code": "000001", "rcept_no": "R1", "rcept_dt": "d", "corp_name": "second"},
    ]
    out = list(
        scan_disclosures(
            _src(items), bgn_de="a", end_de="b", pblntf_ty="B",
            keyword_groups={"spin": ("분할",)}, dedup_key=_dedup,
        )
    )
    assert len(out) == 1
    assert out[0].item["corp_name"] == "first"


@pytest.mark.unit
def test_no_keyword_match_skipped() -> None:
    """어떤 group 키워드도 미매칭 → 제외."""
    items = [{"report_nm": "무관 공시", "stock_code": "000001", "rcept_no": "R1", "rcept_dt": "d"}]
    out = list(
        scan_disclosures(
            _src(items), bgn_de="a", end_de="b", pblntf_ty="B",
            keyword_groups={"spin": ("분할",)}, dedup_key=_dedup,
        )
    )
    assert out == []


@pytest.mark.unit
def test_source_callable_satisfies_port() -> None:
    """주입 source(callable) 가 DisclosureSourcePort 를 만족."""
    assert isinstance(_src([]), DisclosureSourcePort)
