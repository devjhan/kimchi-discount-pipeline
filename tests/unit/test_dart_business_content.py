"""infrastructure/dart — 사업보고서 "사업의 내용" 추출/탐색 단위 테스트 (Task 8).

라이브 DART document endpoint 는 미검증(네트워크). 본 테스트는 추출 로직을 합성
fixture(인코딩·태그·섹션 구조 모사)로, rcept_no 탐색을 stub 공시 list 로 검증한다.
운영 투입 전 실제 보고서로 extract_business_content_from_document 검증 필요.
"""
from __future__ import annotations

import io
import zipfile

import pytest

from infrastructure.dart import client as dart

pytestmark = pytest.mark.unit


def _make_doc_zip(markup: str, *, encoding: str = "cp949") -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("report.xml", markup.encode(encoding))
    return buf.getvalue()


_DOC = (
    "<DOCUMENT>"
    "<SECTION-1><TITLE>I. 회사의 개요</TITLE><P>회사 개요 문단.</P></SECTION-1>"
    "<SECTION-2><TITLE>II. 사업의 내용</TITLE>"
    "<P>당사는 지주회사로서 자회사 지분을 보유하며 NAV 대비 할인 거래된다.</P></SECTION-2>"
    "<SECTION-3><TITLE>III. 재무에 관한 사항</TITLE><P>재무제표 본문.</P></SECTION-3>"
    "</DOCUMENT>"
)


def test_extract_business_content_isolates_section_cp949() -> None:
    text = dart.extract_business_content_from_document(_make_doc_zip(_DOC, encoding="cp949"))
    assert "지주회사" in text
    assert "NAV 대비 할인" in text
    assert "재무제표 본문" not in text  # 다음 섹션 경계에서 절단
    assert "<" not in text  # 태그 제거


def test_extract_business_content_utf8() -> None:
    text = dart.extract_business_content_from_document(_make_doc_zip(_DOC, encoding="utf-8"))
    assert "지주회사" in text


def test_extract_prefers_real_section_over_toc() -> None:
    # 실제 DART 목차는 섹션 제목을 연속 나열("II. 사업의 내용" 다음 줄 "III. 재무에 관한
    # 사항") → 목차의 '사업의 내용' segment 는 곧장 다음 섹션 제목에서 잘려 짧다. 실제 섹션
    # (본문 보유)이 가장 길어 채택된다.
    doc = (
        "<DOCUMENT>"
        "<TOC><P>II. 사업의 내용</P><P>III. 재무에 관한 사항</P></TOC>"
        "<SECTION><TITLE>II. 사업의 내용</TITLE>"
        "<P>실제 본문: 특수상황 지주사 영위 현황 상세.</P></SECTION>"
        "<SECTION><TITLE>III. 재무에 관한 사항</TITLE><P>재무제표 표.</P></SECTION>"
        "</DOCUMENT>"
    )
    text = dart.extract_business_content_from_document(_make_doc_zip(doc))
    assert "실제 본문" in text
    assert "재무제표 표" not in text  # 다음 섹션 경계에서 절단


def test_extract_skips_cross_reference_picks_longest_real_section() -> None:
    # 라이브 검증 발견(LG 003550 / 삼성전자 005930): 마지막 '사업의 내용' 등장은 후속
    # 섹션의 상호참조("앞의 '사업의 내용'을 참조")라 rfind 는 참조 문구를 잡는다. 상호참조
    # 신호('/"/>/참조/참고)를 제외하고 본문이 가장 긴 실제 섹션을 채택해야 한다.
    doc = (
        "<DOCUMENT>"
        "<SECTION><TITLE>II. 사업의 내용</TITLE>"
        "<P>실제 본문: 특수상황 지주사 자회사 NAV 할인 상세 설명 단락.</P></SECTION>"
        "<SECTION><TITLE>III. 재무에 관한 사항</TITLE><P>표.</P></SECTION>"
        "<SECTION><TITLE>XI. 그 밖에 필요한 사항</TITLE>"
        "<P>자세한 내용은 앞의 '사업의 내용'을 참고하시기 바랍니다.</P></SECTION>"
        "</DOCUMENT>"
    )
    text = dart.extract_business_content_from_document(_make_doc_zip(doc))
    assert "실제 본문" in text
    assert "참고하시기" not in text  # 마지막 등장(상호참조)은 채택하지 않음


def test_extract_marker_absent_returns_empty() -> None:
    doc = "<DOCUMENT><TITLE>I. 회사의 개요</TITLE><P>개요만 존재.</P></DOCUMENT>"
    assert dart.extract_business_content_from_document(_make_doc_zip(doc)) == ""


def test_extract_max_chars_truncation() -> None:
    doc = "<P>사업의 내용 " + ("가" * 5000) + "</P>"
    text = dart.extract_business_content_from_document(_make_doc_zip(doc), max_chars=100)
    assert len(text) == 100


def test_extract_bad_zip_returns_empty() -> None:
    assert dart.extract_business_content_from_document(b"not-a-zip") == ""


def test_find_latest_annual_report_picks_most_recent(monkeypatch) -> None:
    items = [
        {"report_nm": "사업보고서 (2022.12)", "rcept_no": "20230315000111", "rcept_dt": "20230315"},
        {"report_nm": "분기보고서 (2023.03)", "rcept_no": "20230515000222", "rcept_dt": "20230515"},
        {"report_nm": "사업보고서 (2023.12)", "rcept_no": "20240314000333", "rcept_dt": "20240314"},
    ]
    monkeypatch.setattr(dart, "iter_disclosures", lambda *a, **k: iter(items))
    rcept = dart.find_latest_annual_report_rcept_no(
        "key", corp_code="00126380", bgn_de="2023-01-01", end_de="2024-12-31"
    )
    assert rcept == "20240314000333"  # 최신 '사업보고서' (분기보고서 제외)


def test_find_latest_annual_report_none_when_absent(monkeypatch) -> None:
    monkeypatch.setattr(
        dart, "iter_disclosures",
        lambda *a, **k: iter([{"report_nm": "분기보고서", "rcept_no": "x", "rcept_dt": "20240101"}]),
    )
    assert (
        dart.find_latest_annual_report_rcept_no(
            "key", corp_code="x", bgn_de="2023-01-01", end_de="2024-12-31"
        )
        is None
    )


@pytest.mark.live
def test_live_business_content_extraction_real_report() -> None:
    """라이브 검증(재현 가능): 실제 사업보고서에서 '사업의 내용' 본문 추출.

    기본 skip — ``RUN_DART_LIVE=1`` + ``.env`` 의 DART_API_KEY 가 있을 때만 실행
    (네트워크). G21: API key 값은 어디에도 출력하지 않는다. 운영 큐레이션 전 추출
    휴리스틱이 실제 보고서에서 동작하는지 보증 (ad-hoc 검증은 applications.
    verify_dart_business_content 하네스).
    """
    import os
    from datetime import date, timedelta

    from infrastructure._common import utils as _utils

    if not os.environ.get("RUN_DART_LIVE"):
        pytest.skip("RUN_DART_LIVE 미설정 — 라이브 네트워크 테스트 skip")
    env = _utils.load_env_file()
    if not dart.has_dart_key(env):
        pytest.skip("DART_API_KEY 부재 — 라이브 검증 불가")

    api_key = env["DART_API_KEY"]  # G21: 값 비노출.
    cache = _utils.repo_path(".cache", "dart") / "corp_index.json"
    corp_code = dart.load_or_fetch_corp_code_index(api_key, cache).get("005930")
    assert corp_code, "삼성전자 corp_code 매핑 부재"

    end = date.today()
    bgn = end - timedelta(days=550)
    text = dart.fetch_business_content(
        api_key,
        corp_code=corp_code,
        bgn_de=bgn.strftime("%Y%m%d"),
        end_de=end.strftime("%Y%m%d"),
    )
    # 실제 '사업의 내용' 섹션은 상호참조 문구(수십 자)보다 훨씬 길다.
    assert len(text) > 1000
    assert "<" not in text  # 태그 제거
    assert "사업의 내용" in text[:20]  # 실제 섹션 머리에서 시작
