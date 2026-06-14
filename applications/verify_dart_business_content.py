"""DART '사업의 내용' 라이브 검증 하네스 (ADR-0013 open item — Task 7).

실제 DART ``document.xml`` endpoint 로 한 종목의 최신 사업보고서를 받아
``extract_business_content_from_document`` 추출 휴리스틱이 실제 보고서에서 동작하는지
검증한다. 합성 fixture(test_dart_business_content.py)는 추출 *로직* 만 고정하므로, 실제
포맷(인코딩·태그·섹션 제목 변형)에 대한 검증은 본 하네스가 담당한다.

사용:
    python -m applications.verify_dart_business_content --stock 005930
    python -m applications.verify_dart_business_content --stock 003550 --stock 028260

G21: DART_API_KEY 값은 본문/stdout/로그에 절대 노출하지 않는다 (존재 여부만 보고). 추출된
보고서 본문은 secret 이 아니라 공개 공시 텍스트이므로 일부 미리보기를 출력한다.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta

from infrastructure._common import utils as _utils
from infrastructure.dart import client as _dart


def _resolve_corp_code(api_key: str, stock: str) -> str | None:
    cache_path = _utils.repo_path(".cache", "dart") / "corp_index.json"
    try:
        index = _dart.load_or_fetch_corp_code_index(api_key, cache_path)
    except _dart.DartUnavailable as exc:
        print(f"  corp_index 로드 실패: {exc}")
        return None
    return index.get(stock)


def _verify_one(api_key: str, stock: str) -> bool:
    print(f"\n=== stock_code={stock} ===")
    corp_code = _resolve_corp_code(api_key, stock)
    if not corp_code:
        print("  corp_code 매핑 부재 — skip")
        return False
    print(f"  corp_code={corp_code}")

    end = date.today()
    bgn = end - timedelta(days=550)  # 최근 ~1.5년 (연 1회 사업보고서 포함 보장)
    bgn_de, end_de = bgn.strftime("%Y%m%d"), end.strftime("%Y%m%d")

    rcept_no = _dart.find_latest_annual_report_rcept_no(
        api_key, corp_code=corp_code, bgn_de=bgn_de, end_de=end_de
    )
    if not rcept_no:
        print(f"  사업보고서 부재 (기간 {bgn_de}~{end_de}) — skip")
        return False
    print(f"  latest 사업보고서 rcept_no={rcept_no}")

    try:
        text = _dart.fetch_business_content(
            api_key, corp_code=corp_code, bgn_de=bgn_de, end_de=end_de
        )
    except _dart.DartUnavailable as exc:
        print(f"  추출 실패: {exc}")
        return False

    _ok = bool(text) and "사업의 내용" not in text[:50]  # 마커 자체가 본문 머리에 안 남았는지
    print(f"  추출 본문 길이={len(text)}자")
    print(f"  미리보기(앞 240자): {text[:240]!r}")
    print(f"  '<' 태그 잔존 여부: {'<' in text}")
    print(f"  판정: {'OK' if text else 'EMPTY'}")
    return bool(text)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="applications.verify_dart_business_content")
    parser.add_argument(
        "--stock", action="append", default=None,
        help="6자리 종목코드 (반복 지정 가능). 기본: 005930(삼성전자) 003550(LG) 028260(삼성물산)",
    )
    args = parser.parse_args(argv)
    stocks = args.stock or ["005930", "003550", "028260"]

    env = _utils.load_env_file()
    if not _dart.has_dart_key(env):
        print("DART_API_KEY 미설정 (.env) — 라이브 검증 불가. 합성 fixture 테스트만 유효.")
        return 1
    api_key = env["DART_API_KEY"]  # G21: 값은 출력하지 않음.
    print("DART_API_KEY: present (값 비표시 — G21)")

    results = {s: _verify_one(api_key, s) for s in stocks}
    ok_count = sum(1 for v in results.values() if v)
    print(f"\n=== 요약: {ok_count}/{len(results)} 종목 본문 추출 성공 ===")
    return 0 if ok_count else 2


if __name__ == "__main__":
    sys.exit(main())
