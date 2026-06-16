"""infrastructure/dart — 'IV. 이사의 경영진단 및 분석의견'(MD&A) 추출 단위 테스트 (Task 6).

semantic 임베딩 텍스트 source 를 운영 사실(사업의 내용)에서 경영진의 추세·전망 서술
(MD&A)로 전환한다 (핸드오프 §4 결정 2-a). 본 테스트는 추출 *로직* 을 합성 fixture
(인코딩·태그·섹션 구조·상호참조 모사)로 고정한다. 실제 보고서 검증은 라이브 하네스
(applications.verify_dart_business_content --section mda) 책임.
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


# 서식 순서: III. 재무에 관한 사항 → IV. 이사의 경영진단 및 분석의견(MD&A) →
#            V. 회계감사인의 감사의견 등.
_MDA_DOC = (
    "<DOCUMENT>"
    "<SECTION><TITLE>III. 재무에 관한 사항</TITLE><P>재무제표 본문 수치 표.</P></SECTION>"
    "<SECTION><TITLE>IV. 이사의 경영진단 및 분석의견</TITLE>"
    "<P>당사 경영진은 지주회사 전환 이후 자회사 실적과 배당정책을 분석한다. "
    "유동성과 재무구조는 안정적이다.</P></SECTION>"
    "<SECTION><TITLE>V. 회계감사인의 감사의견 등</TITLE><P>감사의견 적정.</P></SECTION>"
    "</DOCUMENT>"
)


def test_extract_mda_isolates_section_cp949() -> None:
    text = dart.extract_mda_from_document(_make_doc_zip(_MDA_DOC, encoding="cp949"))
    assert "경영진은" in text
    assert "배당정책" in text
    assert "감사의견 적정" not in text  # 다음 섹션(회계감사인의 감사의견) 경계에서 절단
    assert "재무제표 본문" not in text  # MD&A 마커 이전(재무에 관한 사항)은 미포함
    assert "<" not in text  # 태그 제거


def test_extract_mda_utf8() -> None:
    text = dart.extract_mda_from_document(_make_doc_zip(_MDA_DOC, encoding="utf-8"))
    assert "경영진은" in text


def test_extract_mda_skips_cross_reference_picks_real_section() -> None:
    # 라이브 검증 발견(사업의 내용과 동형): 마지막 'IV. 이사의 경영진단' 등장은 후속 섹션의
    # 상호참조("앞의 '이사의 경영진단 및 분석의견'을 참고")라 단순 rfind 는 참조 문구를
    # 잡는다. 상호참조 신호('/"/참조/참고)를 제외하고 본문이 가장 긴 실제 섹션을 채택해야
    # 한다. xref segment 를 의도적으로 길게 둬도(아래 반복 문구) 채택되면 안 된다.
    doc = (
        "<DOCUMENT>"
        "<SECTION><TITLE>IV. 이사의 경영진단 및 분석의견</TITLE>"
        "<P>실제 본문: 경영진단 상세 분석, 유동성 위험과 재무구조 평가 단락 전개.</P></SECTION>"
        "<SECTION><TITLE>V. 회계감사인의 감사의견</TITLE><P>적정.</P></SECTION>"
        "<SECTION><TITLE>XI. 그 밖에 투자자 보호를 위하여 필요한 사항</TITLE>"
        "<P>자세한 내용은 앞의 '이사의 경영진단 및 분석의견'을 참고하시기 바랍니다. "
        + ("추가 안내 문구 " * 60)
        + "</P></SECTION>"
        "</DOCUMENT>"
    )
    text = dart.extract_mda_from_document(_make_doc_zip(doc))
    assert "실제 본문" in text
    assert "참고하시기" not in text  # 상호참조(마지막·최장 등장)는 채택하지 않음


def test_extract_mda_prefers_real_section_over_toc() -> None:
    doc = (
        "<DOCUMENT>"
        "<TOC><P>IV. 이사의 경영진단 및 분석의견</P><P>V. 회계감사인의 감사의견</P></TOC>"
        "<SECTION><TITLE>IV. 이사의 경영진단 및 분석의견</TITLE>"
        "<P>실제 본문: 경영진단 상세 평가 단락.</P></SECTION>"
        "<SECTION><TITLE>V. 회계감사인의 감사의견</TITLE><P>적정.</P></SECTION>"
        "</DOCUMENT>"
    )
    text = dart.extract_mda_from_document(_make_doc_zip(doc))
    assert "실제 본문" in text
    assert "적정" not in text  # 다음 섹션 경계에서 절단


def test_extract_mda_marker_absent_returns_empty() -> None:
    doc = "<DOCUMENT><TITLE>I. 회사의 개요</TITLE><P>개요만 존재.</P></DOCUMENT>"
    assert dart.extract_mda_from_document(_make_doc_zip(doc)) == ""


def test_extract_mda_max_chars_truncation() -> None:
    doc = "<P>이사의 경영진단 " + ("가" * 5000) + "</P>"
    text = dart.extract_mda_from_document(_make_doc_zip(doc), max_chars=100)
    assert len(text) == 100


def test_extract_mda_bad_zip_returns_empty() -> None:
    assert dart.extract_mda_from_document(b"not-a-zip") == ""


def test_business_and_mda_are_independent_sections() -> None:
    # 'II. 사업의 내용' + 'IV. 이사의 경영진단' 둘 다 가진 문서에서 각 추출기가 자기 섹션만.
    doc = (
        "<DOCUMENT>"
        "<SECTION><TITLE>II. 사업의 내용</TITLE>"
        "<P>사업 본문: 지주회사 자회사 지분 보유 현황.</P></SECTION>"
        "<SECTION><TITLE>III. 재무에 관한 사항</TITLE><P>재무 표.</P></SECTION>"
        "<SECTION><TITLE>IV. 이사의 경영진단 및 분석의견</TITLE>"
        "<P>경영진단 본문: 배당 확대와 지배구조 개편 전망.</P></SECTION>"
        "<SECTION><TITLE>V. 회계감사인의 감사의견</TITLE><P>적정.</P></SECTION>"
        "</DOCUMENT>"
    )
    z = _make_doc_zip(doc)
    biz = dart.extract_business_content_from_document(z)
    mda = dart.extract_mda_from_document(z)
    assert "사업 본문" in biz and "경영진단 본문" not in biz
    assert "경영진단 본문" in mda and "사업 본문" not in mda


def test_fetch_mda_integration(monkeypatch) -> None:
    monkeypatch.setattr(
        dart, "find_latest_annual_report_rcept_no", lambda *a, **k: "20240314000333"
    )
    monkeypatch.setattr(
        dart, "_download_document_zip", lambda *a, **k: _make_doc_zip(_MDA_DOC)
    )
    text = dart.fetch_mda(
        "key", corp_code="00126380", bgn_de="2023-01-01", end_de="2024-12-31"
    )
    assert "경영진은" in text


def test_fetch_mda_raises_when_no_report(monkeypatch) -> None:
    monkeypatch.setattr(
        dart, "find_latest_annual_report_rcept_no", lambda *a, **k: None
    )
    with pytest.raises(dart.DartUnavailable):
        dart.fetch_mda("key", corp_code="x", bgn_de="2023-01-01", end_de="2024-12-31")


def test_fetch_mda_raises_when_extract_empty(monkeypatch) -> None:
    doc = "<DOCUMENT><TITLE>I. 회사의 개요</TITLE><P>개요만.</P></DOCUMENT>"
    monkeypatch.setattr(
        dart, "find_latest_annual_report_rcept_no", lambda *a, **k: "20240314000333"
    )
    monkeypatch.setattr(dart, "_download_document_zip", lambda *a, **k: _make_doc_zip(doc))
    with pytest.raises(dart.DartUnavailable):
        dart.fetch_mda("key", corp_code="x", bgn_de="2023-01-01", end_de="2024-12-31")
