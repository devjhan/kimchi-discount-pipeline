"""
tests/unit/test_holding_subsidiaries_parser.py — DART 타법인 출자현황 parser 검증.

Covered:
    - _normalize_corp_name: (주) / 주식회사 prefix strip
    - _parse_pct: '15.20' / '15.20%' / '-' / '12,345' / None / 음수 / >100 처리
    - _build_name_to_stock: corp_index → name lookup mapping
    - parse_subsidiary_table: DART API monkeypatch 로 mock 응답 검증
    - merge_with_manual_ssot: manual 우선 정책 + ticker 결정 실패 skip
"""

from __future__ import annotations

from typing import Any

import pytest

from infrastructure.dart import holding_subsidiaries_parser as hsp


# --- _normalize_corp_name --------------------------------------------------


def test_normalize_strip_jusik_paren():
    assert hsp._normalize_corp_name("(주)LG화학") == "LG화학"


def test_normalize_strip_jusikhuysa():
    assert hsp._normalize_corp_name("주식회사 카카오") == "카카오"


def test_normalize_no_prefix():
    assert hsp._normalize_corp_name("삼성전자") == "삼성전자"


def test_normalize_trims_whitespace():
    assert hsp._normalize_corp_name("  LG에너지솔루션  ") == "LG에너지솔루션"


# --- _parse_pct ------------------------------------------------------------


def test_parse_pct_basic():
    assert hsp._parse_pct("15.20") == pytest.approx(0.152, abs=1e-6)


def test_parse_pct_with_percent():
    assert hsp._parse_pct("15.20%") == pytest.approx(0.152, abs=1e-6)


def test_parse_pct_with_comma():
    # DART 응답에서 천 단위 콤마 발견 사례
    assert hsp._parse_pct("12,345") is None  # 100 초과 → 거부


def test_parse_pct_none_or_dash():
    assert hsp._parse_pct(None) is None
    assert hsp._parse_pct("-") is None
    assert hsp._parse_pct("") is None


def test_parse_pct_invalid_string():
    assert hsp._parse_pct("abc") is None


def test_parse_pct_negative_rejected():
    assert hsp._parse_pct("-3.5") is None


def test_parse_pct_over_100_rejected():
    assert hsp._parse_pct("150.0") is None


# --- _build_name_to_stock --------------------------------------------------


def test_build_name_to_stock_basic():
    idx = [
        {"stock_code": "051910", "corp_name": "LG화학", "corp_code": "x"},
        {"stock_code": "005930", "corp_name": "삼성전자", "corp_code": "y"},
    ]
    out = hsp._build_name_to_stock(idx)
    assert out["LG화학"] == ["051910"]
    assert out["삼성전자"] == ["005930"]


def test_build_name_to_stock_dedupe_collision():
    # 동일 normalize 이름이 여러 stock 에 매칭 → list 보존
    idx = [
        {"stock_code": "111111", "corp_name": "(주)테스트", "corp_code": "x"},
        {"stock_code": "222222", "corp_name": "테스트", "corp_code": "y"},
    ]
    out = hsp._build_name_to_stock(idx)
    assert sorted(out["테스트"]) == ["111111", "222222"]


# --- parse_subsidiary_table (mock DART) -----------------------------------


def test_parse_subsidiary_no_api_key():
    entries, warnings = hsp.parse_subsidiary_table(
        "00126380", bsns_year="2024", env={}
    )
    assert entries == []
    assert any("DART_API_KEY missing" in w for w in warnings)


def test_parse_subsidiary_with_mock_rows(monkeypatch):
    """DART fetch_other_corp_investment monkeypatch 후 본 parser 검증."""
    mock_rows = [
        {
            "inv_prm": "LG화학",
            "trmend_blce_qy": "21,500,000",
            "trmend_blce_qota_rt": "30.50",
            "bsis_blce_qota_rt": "30.50",
        },
        {
            "inv_prm": "비상장자회사",
            "trmend_blce_qota_rt": "100.00",
        },
        {
            "inv_prm": "LG화학",  # 중복 — name_to_stock 매칭 ambiguous 처리
            "trmend_blce_qota_rt": "0.50",  # 별도 row
        },
    ]
    monkeypatch.setattr(
        hsp,
        "fetch_other_corp_investment",
        lambda *args, **kwargs: mock_rows,
    )
    corp_index = [
        {"stock_code": "051910", "corp_name": "LG화학", "corp_code": "y"},
    ]
    entries, warnings = hsp.parse_subsidiary_table(
        "00126380",
        bsns_year="2024",
        env={"DART_API_KEY": "fake"},
        corp_full_index=corp_index,
    )
    assert len(entries) == 3
    # 첫 entry: LG화학 listed 매칭 성공
    e0 = entries[0]
    assert e0["stock_code"] == "051910"
    assert e0["listed"] is True
    assert e0["ownership_pct"] == pytest.approx(0.305, abs=1e-4)
    assert e0["confidence"] == "auto_parsed_high"
    # 두번째: 비상장자회사 — 매칭 실패
    e1 = entries[1]
    assert e1["stock_code"] is None
    assert e1["listed"] is False
    assert e1["confidence"] == "auto_parsed_low"


def test_parse_subsidiary_empty_rows(monkeypatch):
    monkeypatch.setattr(
        hsp, "fetch_other_corp_investment", lambda *args, **kwargs: []
    )
    entries, warnings = hsp.parse_subsidiary_table(
        "00126380", bsns_year="2024", env={"DART_API_KEY": "fake"}
    )
    assert entries == []
    assert any("empty" in w for w in warnings)


def test_parse_subsidiary_api_failure_graceful(monkeypatch):
    from infrastructure.dart.client import DartUnavailable

    def boom(*args, **kwargs):
        raise DartUnavailable("simulated 503")

    monkeypatch.setattr(hsp, "fetch_other_corp_investment", boom)
    entries, warnings = hsp.parse_subsidiary_table(
        "00126380", bsns_year="2024", env={"DART_API_KEY": "fake"}
    )
    assert entries == []
    assert any("fetch fail" in w for w in warnings)


# --- merge_with_manual_ssot -----------------------------------------------


def test_merge_manual_first_then_auto():
    manual = [
        {
            "stock_code": "051910",
            "name": "LG화학",
            "ownership_pct": 0.305,
            "listed": True,
        }
    ]
    auto = [
        {
            "stock_code": "051910",  # manual 과 같음 → skip
            "name": "LG화학",
            "ownership_pct": 0.305,
            "listed": True,
            "confidence": "auto_parsed_high",
        },
        {
            "stock_code": "066570",  # 새 entry
            "name": "LG전자",
            "ownership_pct": 0.331,
            "listed": True,
            "confidence": "auto_parsed_high",
        },
    ]
    merged, warnings = hsp.merge_with_manual_ssot(auto, manual)
    assert len(merged) == 2
    assert merged[0]["stock_code"] == "051910"
    assert merged[0]["confidence"] == "manual_ssot"
    assert merged[1]["stock_code"] == "066570"
    assert merged[1]["confidence"] == "auto_parsed_high"


def test_merge_skips_low_confidence():
    manual: list[dict[str, Any]] = []
    auto = [
        {
            "stock_code": None,  # ticker 결정 실패
            "name": "외국법인",
            "ownership_pct": 0.5,
            "listed": False,
            "confidence": "auto_parsed_low",
        }
    ]
    merged, warnings = hsp.merge_with_manual_ssot(auto, manual)
    assert merged == []
    assert any("skipped (ticker 자동 결정 실패)" in w for w in warnings)
