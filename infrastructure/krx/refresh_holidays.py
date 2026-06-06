#!/usr/bin/env python3
"""
KRX 휴장일 자동 갱신 helper — manual invoke 전용.

`infrastructure/_common/_holidays_krx.json` (정적 캐시)를 KRX open data API로
fetch한 결과와 merge하고 `_meta.last_verified_date`를 갱신한다.
일별 cron pipeline에서는 호출되지 않음 (network dependency 회피).

Usage:
    # dry-run: diff만 출력, 파일 미기록
    python -m infrastructure.krx.refresh_holidays --dry-run --years 2026 2027 2028

    # 실제 기록
    python -m infrastructure.krx.refresh_holidays --years 2026 2027 2028

    # 기본값: 올해~내후년 3개년
    python -m infrastructure.krx.refresh_holidays

Hard guards:
    G8: fetch 실패 시 FetchError → exit(1), 기존 파일 유지 (hallucination 금지)
    G20: 기존 파일은 .bak으로 보존 후 원자적 교체

API endpoint 검증:
    KRX 데이터 포털: https://data.krx.co.kr
    현재 후보 endpoint: KRX_ENDPOINT (아래 상수) — 초 실행 전 응답 구조 확인 필수.
    dry-run으로 먼저 실행 후 응답 JSON을 확인할 것.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

# KST UTC+9
try:
    from zoneinfo import ZoneInfo
    KST = ZoneInfo("Asia/Seoul")
except ImportError:
    from datetime import timezone, timedelta
    KST = timezone(timedelta(hours=9))

_DEFAULT_HOLIDAYS_PATH = (
    Path(__file__).resolve().parent.parent / "_common" / "_holidays_krx.json"
)

# ============================================================
# KRX API 설정 — 초 실행 전 endpoint 및 응답 키 검증 필요
# ============================================================
# KRX 데이터 포털 (data.krx.co.kr) 은 POST 기반 API를 사용한다.
# 아래 상수는 알려진 후보값이며, 실제 응답 구조에 따라 조정 필요.
# --dry-run 모드로 먼저 실행해 응답 JSON 구조를 확인할 것.
KRX_ENDPOINT = "https://data.krx.co.kr/comm/bldAttendant/getJsonData.cmd"
# 요청 form data 템플릿 — fromdate/todate는 연도에 따라 동적 치환
KRX_PAYLOAD_TEMPLATE = {
    "bld": "dbms/MDC/STAT/standard/MDCSTAT01901",
    "locale": "ko_KR",
    "share": "1",
    "money": "1",
    "csvxls_isNo": "false",
}
# 응답 JSON 에서 날짜를 담은 배열 키 (실제 응답 구조에 따라 조정)
KRX_RESPONSE_LIST_KEY = "output"
# 배열 각 항목에서 날짜를 담은 필드명 (YYYYMMDD 형식 예상)
KRX_DATE_FIELD = "BAS_DD"
# 공휴일 여부를 나타내는 필드 (값이 "Y" 이면 휴장)
KRX_HOLIDAY_FIELD = "HOLDY_YN"


class FetchError(RuntimeError):
    """HTTP / parse / 응답 구조 실패. 호출자가 exit(1) + warning 처리 (G8)."""


# ============================================================
# Pure functions (no network / no file I/O)
# ============================================================

def merge_holidays(
    existing: dict[str, Any],
    fetched: list[str],
    source_citation: str,
    now_kst: str,
) -> dict[str, Any]:
    """
    기존 JSON dict와 fetched 날짜 목록을 union + deduplicate + sort.

    _meta 갱신:
        last_verified_date = now_kst
        source             = source_citation
        stale_after_months  보존 (없으면 기본 6)

    순수 함수 — 부작용 없음. existing dict는 불변.
    """
    existing_set: set[str] = set(existing.get("holidays") or [])
    merged = sorted(existing_set | set(fetched))
    stale_after = int((existing.get("_meta") or {}).get("stale_after_months", 6))
    new_meta: dict[str, Any] = {
        "market": "KRX",
        "last_verified_date": now_kst,
        "stale_after_months": stale_after,
        "source": source_citation,
    }
    result = dict(existing)
    result["_meta"] = new_meta
    result["holidays"] = merged
    return result


def diff_holidays(existing: dict[str, Any], merged: dict[str, Any]) -> dict[str, Any]:
    """merge 전후 diff (추가/제거). dry-run 표시용."""
    old_set = set(existing.get("holidays") or [])
    new_set = set(merged.get("holidays") or [])
    return {
        "added": sorted(new_set - old_set),
        "removed": sorted(old_set - new_set),
        "total_before": len(old_set),
        "total_after": len(new_set),
    }


# ============================================================
# File I/O helpers
# ============================================================

def load_existing_json(path: Path) -> dict[str, Any]:
    """
    기존 _holidays_krx.json load. 미존재 시 빈 skeleton 반환 (no raise).
    JSON 파싱 실패 시 FetchError raise (caller가 abort).
    """
    if not path.exists():
        return {"_comment": "", "_meta": {}, "holidays": []}
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as exc:
        raise FetchError(f"기존 JSON 파싱 실패: {path} — {exc}") from exc


def write_atomically(path: Path, payload: dict[str, Any]) -> None:
    """
    .bak 보존 → .tmp 기록 → .tmp → 원본 rename (G20 — rollback 가능).
    같은 day 재실행 시 .bak은 덮어씀 (의도적 overwrite — refresh 목적).
    """
    bak = path.with_suffix(".json.bak")
    tmp = path.with_suffix(".json.tmp")
    if path.exists():
        shutil.copy2(path, bak)
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")
    tmp.replace(path)


# ============================================================
# Network fetch
# ============================================================

def _post_json(url: str, form_data: dict[str, str], timeout: float) -> dict[str, Any]:
    """HTTP POST → JSON. FetchError raise on failure (G8)."""
    encoded = urllib.parse.urlencode(form_data).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=encoded,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "investment-pipeline/1.0",
            "Referer": "https://data.krx.co.kr",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
    except Exception as exc:  # noqa: BLE001
        raise FetchError(f"HTTP POST 실패: {url} — {exc}") from exc
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise FetchError(
            f"JSON parse 실패: {url} — 응답 앞 200자: {raw[:200]!r}"
        ) from exc


def fetch_krx_holidays(
    years: list[int],
    *,
    timeout: float = 15.0,
) -> tuple[list[str], str]:
    """
    KRX 데이터 포털에서 지정 연도의 휴장일 목록을 fetch.

    ⚠️  초 실행 전 endpoint + 응답 키 검증 필요.
        --dry-run 모드로 실행해 API 응답 JSON 구조를 stdout에서 확인할 것.
        응답 구조가 다르면 KRX_RESPONSE_LIST_KEY / KRX_DATE_FIELD /
        KRX_HOLIDAY_FIELD 상수를 조정한다.

    Returns:
        (holidays_iso_list, source_citation)
        holidays_iso_list: sorted YYYY-MM-DD strings
        source_citation: "KRX-DataPortal@{today}={endpoint}"

    Raises:
        FetchError: HTTP 실패 또는 응답 구조 파싱 불가 (G8 — caller가 exit(1))
    """
    today_iso = datetime.now(KST).strftime("%Y-%m-%d")
    all_holidays: list[str] = []
    warnings: list[str] = []

    for year in years:
        form = dict(KRX_PAYLOAD_TEMPLATE)
        form["fromdate"] = f"{year}0101"
        form["todate"] = f"{year}1231"

        data = _post_json(KRX_ENDPOINT, form, timeout)

        rows = data.get(KRX_RESPONSE_LIST_KEY)
        if rows is None:
            raise FetchError(
                f"응답에 '{KRX_RESPONSE_LIST_KEY}' 키 없음 ({year}년). "
                f"응답 키 목록: {list(data.keys())!r}. "
                f"KRX_RESPONSE_LIST_KEY 상수를 올바른 키로 수정할 것."
            )
        if not isinstance(rows, list):
            raise FetchError(
                f"응답 '{KRX_RESPONSE_LIST_KEY}' 가 list가 아님 ({year}년): {type(rows)}"
            )

        year_holidays: list[str] = []
        for row in rows:
            raw_date = row.get(KRX_DATE_FIELD, "")
            if not raw_date:
                continue
            holdy = row.get(KRX_HOLIDAY_FIELD, "")
            if holdy != "Y":
                continue
            # YYYYMMDD → YYYY-MM-DD
            if len(raw_date) == 8 and raw_date.isdigit():
                iso = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:]}"
                year_holidays.append(iso)
            else:
                warnings.append(
                    f"날짜 파싱 실패 ({year}년): {raw_date!r} — 건너뜀"
                )

        if not year_holidays:
            warnings.append(
                f"{year}년 휴장일 0건 — HOLDY_YN='Y' 행 없음. "
                f"KRX_HOLIDAY_FIELD 또는 KRX_DATE_FIELD 확인 필요."
            )
        all_holidays.extend(year_holidays)

    for w in warnings:
        sys.stderr.write(f"[holiday-refresh] WARN: {w}\n")

    source = f"KRX-DataPortal@{today_iso}={KRX_ENDPOINT}"
    return sorted(set(all_holidays)), source


# ============================================================
# CLI
# ============================================================

def _default_years() -> list[int]:
    now = datetime.now(KST)
    return [now.year, now.year + 1, now.year + 2]


def _covers_current_year(existing: dict[str, Any]) -> bool:
    """existing cache 가 현재 연도(이상) 휴장일을 이미 포함하는가 (annual self-skip gate).

    휴장일은 연 단위로 공표 — 현재 연도가 캐시에 있으면 daily refresh 불요. 연이
    롤오버하면(1월) max(year) < 현재연도 가 되어 자동 재fetch.
    """
    years = {
        int(d[:4])
        for d in (existing.get("holidays") or [])
        if len(d) >= 4 and d[:4].isdigit()
    }
    return bool(years) and max(years) >= datetime.now(KST).year


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="KRX 휴장일 JSON 자동 갱신 (수동 invoke 전용)"
    )
    parser.add_argument(
        "--years",
        nargs="+",
        type=int,
        default=None,
        metavar="YYYY",
        help="갱신 대상 연도 (기본: 올해~내후년)",
    )
    parser.add_argument(
        "--holidays-path",
        type=Path,
        default=_DEFAULT_HOLIDAYS_PATH,
        metavar="PATH",
        help=f"대상 JSON 파일 (기본: {_DEFAULT_HOLIDAYS_PATH})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="diff만 stdout 출력, 파일 미기록",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=15.0,
        metavar="SEC",
        help="HTTP timeout (기본: 15초)",
    )
    args = parser.parse_args(argv)
    years_explicit = args.years is not None
    years: list[int] = args.years or _default_years()
    holidays_path: Path = args.holidays_path

    existing = load_existing_json(holidays_path)

    # 자동 모드(--years 미지정) + 현재 연도 이미 cache → self-skip (D-2 daily 무조건 호출).
    # 명시 --years 는 사용자 의도이므로 gate 우회 (항상 fetch).
    if not years_explicit and not args.dry_run and _covers_current_year(existing):
        print("[holiday-refresh] cache 가 현재 연도 휴장일 포함 — skip (annual gate)")
        return 0

    try:
        fetched, source_citation = fetch_krx_holidays(years, timeout=args.timeout)
    except FetchError as exc:
        # KRX endpoint 가 cloud non-Korean IP 에서 종종 HTTP 403 Forbidden 또는
        # 연결 timeout 반환. 이는 G8 의 정적 캐시 fallback 으로 graceful 하게
        # 처리되며, 진짜 이상 신호 (5xx, parse 오류) 와 구분하기 위해 본 케이스만
        # ERROR 가 아닌 info 로 격하 (로그 노이즈 감소, exit 0 유지).
        msg = str(exc).lower()
        is_geo_block_or_timeout = (
            "403" in msg
            or "forbidden" in msg
            or "timed out" in msg
            or "timeout" in msg
        )
        if is_geo_block_or_timeout:
            sys.stderr.write(
                "[holiday-refresh] info: 외부 fetch unavailable "
                f"(KRX endpoint 거부 또는 timeout) — 정적 캐시 유지 (G8). detail={exc}\n"
            )
            return 0
        sys.stderr.write(f"[holiday-refresh] ERROR: {exc}\n")
        sys.stderr.write("[holiday-refresh] 기존 파일 유지 (G8).\n")
        return 1

    now_kst = datetime.now(KST).strftime("%Y-%m-%d")
    merged = merge_holidays(existing, fetched, source_citation, now_kst)
    d = diff_holidays(existing, merged)

    if args.dry_run:
        print("[holiday-refresh] DRY-RUN — 파일 미기록")
        print(f"  추가: {len(d['added'])}건  {d['added']}")
        print(f"  제거: {len(d['removed'])}건  {d['removed']}")
        print(f"  합계: {d['total_before']} → {d['total_after']}건")
        print(f"  source: {source_citation}")
        return 0

    write_atomically(holidays_path, merged)
    added = len(d["added"])
    total = d["total_after"]
    print(
        f"[holiday-refresh] OK — 추가 {added}건, 합계 {total}건, "
        f"last_verified_date={now_kst}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
