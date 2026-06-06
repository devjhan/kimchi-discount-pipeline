"""
tests/unit/test_preferred_pairs_parser.py — KRX 우선주/보통주 pair 자동 발견 검증.

Covered:
    - _strip_preferred_suffix: 우/우B/우C/1우B 정규화
    - _preferred_to_common_ticker: 6자리 끝자리 5 → 0 변환
    - discover_pairs_from_corp_index: fake corpCode entries → pair detection
    - merge_with_manual_pairs: manual SSOT 우선 정책
    - 매칭 실패 케이스 (이름 mismatch / common ticker missing) → warnings
"""

from __future__ import annotations

from infrastructure.dart import preferred_pairs_parser as ppp


def _entry(stock: str, name: str) -> dict[str, str]:
    return {"stock_code": stock, "corp_name": name, "corp_code": stock + "00"}


# --- _strip_preferred_suffix ------------------------------------------------


def test_strip_preferred_basic():
    assert ppp._strip_preferred_suffix("삼성전자우") == ("삼성전자", "우")


def test_strip_preferred_b_variant():
    assert ppp._strip_preferred_suffix("CJ제일제당우B") == ("CJ제일제당", "우B")


def test_strip_preferred_numbered():
    assert ppp._strip_preferred_suffix("두산퓨얼셀1우B") == ("두산퓨얼셀", "1우B")


def test_strip_preferred_no_suffix():
    assert ppp._strip_preferred_suffix("삼성전자") == ("삼성전자", None)


# --- _preferred_to_common_ticker -------------------------------------------


def test_preferred_to_common_basic():
    assert ppp._preferred_to_common_ticker("005935") == "005930"


def test_preferred_to_common_lg():
    assert ppp._preferred_to_common_ticker("051915") == "051910"


def test_preferred_to_common_invalid_length():
    assert ppp._preferred_to_common_ticker("12345") is None


def test_preferred_to_common_non_five_suffix():
    # 끝자리 5 아니면 None
    assert ppp._preferred_to_common_ticker("005930") is None


def test_preferred_to_common_non_digit():
    assert ppp._preferred_to_common_ticker("00593A") is None


# --- discover_pairs_from_corp_index ----------------------------------------


def test_discover_basic_pair():
    corp_index = [
        _entry("005930", "삼성전자"),
        _entry("005935", "삼성전자우"),
    ]
    pairs, warnings = ppp.discover_pairs_from_corp_index(corp_index)
    assert len(pairs) == 1
    p = pairs[0]
    assert p["common"] == "005930"
    assert p["preferred"] == "005935"
    assert p["name_preferred"] == "삼성전자우"
    assert p["name_common"] == "삼성전자"
    assert p["confidence"] == "auto_parsed_high"


def test_discover_multiple_pairs_sorted():
    corp_index = [
        _entry("005380", "현대차"),
        _entry("005385", "현대차우"),
        _entry("005930", "삼성전자"),
        _entry("005935", "삼성전자우"),
        _entry("051910", "LG화학"),
        _entry("051915", "LG화학우"),
    ]
    pairs, _ = ppp.discover_pairs_from_corp_index(corp_index)
    preferred_tickers = [p["preferred"] for p in pairs]
    assert preferred_tickers == sorted(preferred_tickers)
    assert len(pairs) == 3


def test_discover_preferred_without_common_warning():
    # 우선주만 있고 보통주 ticker 가 corp_index 에 없음
    corp_index = [
        _entry("005935", "삼성전자우"),
    ]
    pairs, warnings = ppp.discover_pairs_from_corp_index(corp_index)
    assert pairs == []
    assert any("not in corp index" in w for w in warnings)


def test_discover_name_mismatch_skipped():
    # ticker 패턴은 맞지만 이름이 mismatch (역시 흔치 않은 사례)
    corp_index = [
        _entry("005930", "다른회사"),
        _entry("005935", "삼성전자우"),
    ]
    pairs, warnings = ppp.discover_pairs_from_corp_index(corp_index)
    # base name '삼성전자' 가 '다른회사' 에 substring 매칭 실패 → skip
    assert pairs == []
    assert any("name mismatch" in w for w in warnings)


def test_discover_ignores_non_preferred():
    corp_index = [
        _entry("005930", "삼성전자"),
        _entry("000660", "SK하이닉스"),  # 우선주 suffix 없음
    ]
    pairs, _ = ppp.discover_pairs_from_corp_index(corp_index)
    assert pairs == []


# --- merge_with_manual_pairs ----------------------------------------------


def test_merge_manual_only():
    manual = [
        {"common": "005930", "preferred": "005935", "name_common": "삼성전자", "name_preferred": "삼성전자우", "market": "KOSPI"},
    ]
    merged, _ = ppp.merge_with_manual_pairs([], manual)
    assert len(merged) == 1
    assert merged[0]["confidence"] == "manual_ssot"
    assert merged[0]["market"] == "KOSPI"


def test_merge_manual_overrides_auto():
    manual = [
        {"common": "005930", "preferred": "005935", "name_common": "삼성전자", "name_preferred": "삼성전자우", "market": "KOSPI"},
    ]
    auto = [
        {"common": "005930", "preferred": "005935", "name_common": "삼성전자", "name_preferred": "삼성전자우",
         "market": "unknown", "confidence": "auto_parsed_high"},
        {"common": "005380", "preferred": "005385", "name_common": "현대차", "name_preferred": "현대차우",
         "market": "unknown", "confidence": "auto_parsed_high"},
    ]
    merged, _ = ppp.merge_with_manual_pairs(auto, manual)
    assert len(merged) == 2
    # manual entry first
    assert merged[0]["preferred"] == "005935"
    assert merged[0]["confidence"] == "manual_ssot"
    assert merged[0]["market"] == "KOSPI"  # manual 값 유지
    # auto-only entry appended
    assert merged[1]["preferred"] == "005385"
    assert merged[1]["confidence"] == "auto_parsed_high"


def test_merge_empty_inputs():
    merged, warnings = ppp.merge_with_manual_pairs([], [])
    assert merged == []
    assert warnings == []
