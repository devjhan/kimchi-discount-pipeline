"""
infrastructure/dart/client.py — OPEN DART API minimal client.

<!-- legacy-ok -->v1 `scripts/_dart.py` 의 후신.<!-- /legacy-ok --> Stage 1 (Universe) + Stage 3 (Catalyst) 공유.
helper script가 아닌 module이므로 직접 실행 안 함.

DART OPEN API spec: https://opendart.fss.or.kr/guide/main.do

본 module은 endpoint 호출만 담당. 공시 type 분류 / catalyst 발견 룰은 각
domain helper 책임 (단일 책임 원칙).

Hard guards:
- G7: API 응답에 포함된 모든 숫자/공시번호는 해당 응답을 source citation으로 인용
- G8: API 호출 실패 시 DartUnavailable raise — caller가 hallucination 대신 graceful skip
- G21: API key는 caller가 환경변수에서 읽어 함수 인자로 전달, module 내부 저장 금지
"""

from __future__ import annotations

import io
import json
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

from infrastructure._common.utils import FetchError, safe_http_json

DART_BASE = "https://opendart.fss.or.kr/api"
DART_LIST_URL = f"{DART_BASE}/list.json"
DART_FNLTT_SINGL_ACNT_ALL_URL = f"{DART_BASE}/fnlttSinglAcntAll.json"
DART_CORP_CODE_URL = f"{DART_BASE}/corpCode.xml"
DART_PAGE_COUNT_MAX = 100

# DART reprt_code enum (정기보고서 코드):
#   11011 = 사업보고서, 11012 = 반기보고서, 11013 = 1분기보고서, 11014 = 3분기보고서
REPRT_CODE_ANNUAL = "11011"
REPRT_CODE_HALF = "11012"
REPRT_CODE_Q1 = "11013"
REPRT_CODE_Q3 = "11014"

# fs_div: CFS = 연결재무제표, OFS = 별도재무제표
FS_DIV_CONSOLIDATED = "CFS"
FS_DIV_SEPARATE = "OFS"

# DART pblntf_ty enum:
#   A = 정기공시 (사업/반기/분기보고서)
#   B = 주요사항보고서 (자기주식, 분할, 합병, 영업양수도)
#   C = 발행공시
#   D = 지분공시 (5% 보유, 임원 신고)
#   E = 기타공시 (자율공시 등)
#   F = 외부감사관련
#   G = 펀드공시
#   H = 자산유동화
#   I = 거래소공시
#   J = 공정위공시
PBLNTF_TY_MAJOR_REPORT = "B"
PBLNTF_TY_OWNERSHIP = "D"


class DartUnavailable(RuntimeError):
    """DART API 미사용 가능 (key 없음 / HTTP 실패 / status 비정상). caller graceful skip 강제."""


def _dart_get(
    params: dict[str, Any],
    api_key: str,
    *,
    url: str = DART_LIST_URL,
    timeout: float | None = None,
    retry: int = 3,
    backoff_base: float = 2.0,
) -> dict[str, Any]:
    """
    DART OPEN API GET wrapper. api_key 없으면 raise.

    status='000' (success) / '013' (no data — 빈 결과 정상) 외엔 raise.
    `url` 인자로 endpoint 전환 (list.json / fnlttSinglAcntAll.json 등).

    timeout=None 이면 endpoint 별 default 적용:
      - list.json (시장 전체 페이지) → 20.0s — 5/14 incident 후 상향
      - 그 외 (fnlttSinglAcntAll 등 단일 회사) → 10.0s

    DART 가 transient 503 (Service Unavailable) 을 종종 반환하므로 기본 retry=3
    (worst case wait = 1+2+4 ≈ 7초). 호출 측이 더 빠른 fail-fast 가 필요하면
    retry=0 으로 호출.
    """
    if not api_key:
        raise DartUnavailable("DART_API_KEY missing")
    if timeout is None:
        timeout = 20.0 if url == DART_LIST_URL else 10.0
    full = dict(params)
    full["crtfc_key"] = api_key
    try:
        data = safe_http_json(
            url,
            params=full,
            timeout=timeout,
            retry=retry,
            backoff_base=backoff_base,
        )
    except FetchError as exc:
        raise DartUnavailable(str(exc)) from exc
    status = data.get("status")
    if status not in ("000", "013"):
        raise DartUnavailable(
            f"DART status={status} message={data.get('message')!r}"
        )
    return data


def iter_disclosures(
    api_key: str,
    *,
    bgn_de: str,
    end_de: str,
    pblntf_ty: str | None = None,
    corp_code: str | None = None,
    max_pages: int = 30,
    pause_seconds: float = 0.05,
    max_window_days: int = 90,
) -> Iterable[dict[str, Any]]:
    """
    DART 공시 검색 paginate.

    Args:
        api_key: .env.DART_API_KEY (caller 책임으로 read).
        bgn_de / end_de: 'YYYY-MM-DD' (slash 또는 hyphen 허용; 내부에서 strip).
        pblntf_ty: 공시 type prefix. None이면 전체.
        corp_code: 8자리 DART 고유번호. 지정 시 server-side filter 적용 (단일
            company 공시만 반환) + DART 의 3개월 검색기간 제한 자동 해제 →
            client-side filter 불필요, window chunking 비활성화. None 이면
            전체 시장 스캔 (3개월 cap 강제 → window chunking 활성).
        max_pages: 단일 window 당 page hard cap (안전장치).
        pause_seconds: 호출 간 sleep (rate-limit courtesy).
        max_window_days: corp_code 미지정 시 DART 가 강제하는 검색기간 cap (3개월).
            전체 [bgn_de, end_de] 가 이를 초과하면 내부에서 sequential window 로 분할.
            corp_code 지정 시 무시 (단일 window).

    Yields:
        dict (DART list.json item — corp_code / corp_name / stock_code / report_nm /
              flr_nm / rcept_no / rcept_dt / rm 등).
    """
    bgn_dt = datetime.strptime(bgn_de.replace("-", ""), "%Y%m%d")
    end_dt = datetime.strptime(end_de.replace("-", ""), "%Y%m%d")
    if bgn_dt > end_dt:
        return

    # corp_code 지정 시 단일 window (3개월 cap 해제) — chunking 무효화.
    if corp_code:
        windows = [(bgn_dt, end_dt)]
    else:
        windows = []
        ws = bgn_dt
        while ws <= end_dt:
            we = min(ws + timedelta(days=max_window_days - 1), end_dt)
            windows.append((ws, we))
            ws = we + timedelta(days=1)

    for w_idx, (window_start, window_end) in enumerate(windows):
        page = 1
        while page <= max_pages:
            params: dict[str, Any] = {
                "bgn_de": window_start.strftime("%Y%m%d"),
                "end_de": window_end.strftime("%Y%m%d"),
                "page_no": page,
                "page_count": DART_PAGE_COUNT_MAX,
            }
            if pblntf_ty:
                params["pblntf_ty"] = pblntf_ty
            if corp_code:
                params["corp_code"] = corp_code
            data = _dart_get(params, api_key)
            items = data.get("list") or []
            for item in items:
                yield item
            total_page = int(data.get("total_page", 1))
            if page >= total_page:
                break
            page += 1
            if pause_seconds > 0:
                time.sleep(pause_seconds)
        if pause_seconds > 0 and w_idx + 1 < len(windows):
            time.sleep(pause_seconds)


def has_dart_key(env: dict[str, str]) -> bool:
    """편의 함수 — caller가 graceful skip 분기 결정 시."""
    return bool(env.get("DART_API_KEY", "").strip())


# ============================================================
# 재무제표 — fnlttSinglAcntAll endpoint (Stage 2 stage2_fin_fetch helper 의존)
# ============================================================


def fetch_financial_statements(
    api_key: str,
    *,
    corp_code: str,
    bsns_year: str,
    reprt_code: str = REPRT_CODE_ANNUAL,
    fs_div: str = FS_DIV_CONSOLIDATED,
    timeout: float = 10.0,
) -> list[dict[str, Any]]:
    """
    DART /api/fnlttSinglAcntAll.json — 단일회사 전체 재무제표 fetch.

    Args:
        api_key: .env.DART_API_KEY (caller 책임).
        corp_code: 8자리 DART 고유번호 (corp_code.xml 매핑 결과).
        bsns_year: '2024' 식 4자리.
        reprt_code: 11011(사업)/11012(반기)/11013(1Q)/11014(3Q).
        fs_div: 'CFS'(연결) / 'OFS'(별도).

    Returns:
        DART 응답의 `list` 항목 그대로 (계산 책임 caller로 위임 — G6 helper 단일 책임).
        no data (status='013') 시 [].

    Raises:
        DartUnavailable: api_key 없음 / HTTP / status 비정상.
    """
    if len(bsns_year) != 4 or not bsns_year.isdigit():
        raise DartUnavailable(f"invalid bsns_year={bsns_year!r}")
    if reprt_code not in (REPRT_CODE_ANNUAL, REPRT_CODE_HALF, REPRT_CODE_Q1, REPRT_CODE_Q3):
        raise DartUnavailable(f"invalid reprt_code={reprt_code!r}")
    if fs_div not in (FS_DIV_CONSOLIDATED, FS_DIV_SEPARATE):
        raise DartUnavailable(f"invalid fs_div={fs_div!r}")
    params = {
        "corp_code": corp_code,
        "bsns_year": bsns_year,
        "reprt_code": reprt_code,
        "fs_div": fs_div,
    }
    data = _dart_get(params, api_key, url=DART_FNLTT_SINGL_ACNT_ALL_URL, timeout=timeout)
    if data.get("status") == "013":
        return []
    return list(data.get("list") or [])


# ============================================================
# Corp code 매핑 — 6자리 stock_code (KRX) ↔ 8자리 corp_code (DART)
# ============================================================


def _download_corp_code_zip(
    api_key: str, *, timeout: float = 30.0
) -> bytes:
    """DART corpCode.xml endpoint 호출 — ZIP bytes 반환."""
    if not api_key:
        raise DartUnavailable("DART_API_KEY missing")
    params = {"crtfc_key": api_key}
    full_url = f"{DART_CORP_CODE_URL}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(
        full_url, headers={"User-Agent": "investment-pipeline/1.0"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except Exception as exc:  # noqa: BLE001
        raise DartUnavailable(f"corpCode.xml fetch fail: {exc}") from exc


def _parse_corp_code_zip(zip_bytes: bytes) -> dict[str, str]:
    """
    ZIP bytes → {stock_code(6자리): corp_code(8자리)} 매핑.

    상장사 (stock_code 비어있지 않은 항목) 만 포함. 비상장은 제외.
    """
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            names = zf.namelist()
            if not names:
                raise DartUnavailable("corpCode.xml zip is empty")
            xml_bytes = zf.read(names[0])
    except zipfile.BadZipFile as exc:
        raise DartUnavailable(f"corpCode.xml not a zip: {exc}") from exc
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise DartUnavailable(f"corpCode.xml parse fail: {exc}") from exc
    out: dict[str, str] = {}
    for el in root.iter("list"):
        stock = (el.findtext("stock_code") or "").strip()
        corp = (el.findtext("corp_code") or "").strip()
        if stock and len(stock) == 6 and corp:
            out[stock] = corp
    return out


def load_or_fetch_corp_code_index(
    api_key: str,
    cache_path: Path,
    *,
    ttl_seconds: int = 7 * 24 * 3600,
) -> dict[str, str]:
    """
    corp_code 매핑을 cache file에서 load. cache stale (TTL 초과) 또는 미존재 시 DART fetch.

    Cache schema: {"fetched_at": iso, "ttl_seconds": int, "index": {"005930": "00126380", ...}}.

    Args:
        api_key: DART_API_KEY.
        cache_path: cache JSON 파일 경로 (.cache/dart/corp_index.json 권장).
        ttl_seconds: cache TTL (default 7일).

    Raises:
        DartUnavailable: cache stale + api_key 미설정 / fetch 실패.
    """
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    if cache_path.exists():
        try:
            with cache_path.open("r", encoding="utf-8") as f:
                cached = json.load(f)
            fetched_at = cached.get("fetched_at_epoch", 0)
            ttl = int(cached.get("ttl_seconds", ttl_seconds))
            if fetched_at and (time.time() - fetched_at) < ttl:
                idx = cached.get("index") or {}
                if isinstance(idx, dict) and idx:
                    return {str(k): str(v) for k, v in idx.items()}
        except Exception:  # noqa: BLE001 — corrupted cache → re-fetch
            pass
    zip_bytes = _download_corp_code_zip(api_key)
    index = _parse_corp_code_zip(zip_bytes)
    if not index:
        raise DartUnavailable("corpCode.xml parsed empty index")
    payload = {
        "fetched_at_epoch": int(time.time()),
        "ttl_seconds": int(ttl_seconds),
        "index": index,
    }
    tmp = cache_path.with_suffix(cache_path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    tmp.replace(cache_path)
    return index


# ============================================================
# Full corp index (with corp_name) — C4/C5 parser 의존
# ============================================================


def _parse_corp_code_zip_full(zip_bytes: bytes) -> list[dict[str, str]]:
    """
    ZIP bytes → list[{stock_code, corp_code, corp_name, modify_date}].

    상장사 (stock_code 6자리) 만 포함. 비상장은 corpCode.xml 의 일부지만 본
    helper 의 목적 (universe / preferred_pairs) 에 부적합 → 제외.
    """
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            names = zf.namelist()
            if not names:
                raise DartUnavailable("corpCode.xml zip is empty")
            xml_bytes = zf.read(names[0])
    except zipfile.BadZipFile as exc:
        raise DartUnavailable(f"corpCode.xml not a zip: {exc}") from exc
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise DartUnavailable(f"corpCode.xml parse fail: {exc}") from exc
    out: list[dict[str, str]] = []
    for el in root.iter("list"):
        stock = (el.findtext("stock_code") or "").strip()
        corp = (el.findtext("corp_code") or "").strip()
        name = (el.findtext("corp_name") or "").strip()
        modify = (el.findtext("modify_date") or "").strip()
        if stock and len(stock) == 6 and corp and name:
            out.append(
                {
                    "stock_code": stock,
                    "corp_code": corp,
                    "corp_name": name,
                    "modify_date": modify,
                }
            )
    return out


def load_or_fetch_corp_full_index(
    api_key: str,
    cache_path: Path,
    *,
    ttl_seconds: int = 7 * 24 * 3600,
) -> list[dict[str, str]]:
    """
    회사명 포함 corp_code 매핑 list. holding_subsidiaries_parser (회사명 →
    ticker 역매핑) + preferred_pairs_parser (이름 "...우" 패턴 detect) 의 input.

    Cache schema:
        {"fetched_at_epoch": int, "ttl_seconds": int, "entries": [...]}.

    Raises:
        DartUnavailable: cache stale + api_key 미설정 / fetch / parse 실패.
    """
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    if cache_path.exists():
        try:
            with cache_path.open("r", encoding="utf-8") as f:
                cached = json.load(f)
            fetched_at = cached.get("fetched_at_epoch", 0)
            ttl = int(cached.get("ttl_seconds", ttl_seconds))
            if fetched_at and (time.time() - fetched_at) < ttl:
                entries = cached.get("entries") or []
                if isinstance(entries, list) and entries:
                    return [dict(e) for e in entries]
        except Exception:  # noqa: BLE001 — corrupted cache → re-fetch
            pass
    zip_bytes = _download_corp_code_zip(api_key)
    entries = _parse_corp_code_zip_full(zip_bytes)
    if not entries:
        raise DartUnavailable("corpCode.xml parsed empty entries")
    payload = {
        "fetched_at_epoch": int(time.time()),
        "ttl_seconds": int(ttl_seconds),
        "entries": entries,
    }
    tmp = cache_path.with_suffix(cache_path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    tmp.replace(cache_path)
    return entries


# ============================================================
# 사업보고서 주요정보 — 타법인 출자현황 (Stage 1 holding_subsidiaries 의존)
# ============================================================

DART_OTR_CPR_INVESTMENT_URL = f"{DART_BASE}/otrCprInvstmntSttus.json"


def fetch_other_corp_investment(
    api_key: str,
    *,
    corp_code: str,
    bsns_year: str,
    reprt_code: str = REPRT_CODE_ANNUAL,
    timeout: float = 10.0,
) -> list[dict[str, Any]]:
    """
    DART /api/otrCprInvstmntSttus.json — 사업보고서 본문의 "타법인 출자현황" fetch.

    Args:
        api_key: .env.DART_API_KEY.
        corp_code: 8자리 DART 고유번호.
        bsns_year: '2024' 식 4자리.
        reprt_code: 11011(사업)/11012(반기)/11013(1Q)/11014(3Q). 본 endpoint 는
                    사업보고서 (11011) 기준 데이터가 가장 안정적.

    Returns:
        DART list 응답 row list. 빈 응답 (status='013') 시 []. 응답 schema 의
        주요 필드:
            inv_prm                       출자대상회사명
            bsis_blce_qy                  기초잔액 수량(주식수)
            bsis_blce_qota_rt             기초잔액 지분율 (%)
            trmend_blce_qy                기말잔액 수량
            trmend_blce_qota_rt           기말잔액 지분율 (%)
            recent_bsns_year_fnnr_sttus_tot_assets       자산총계
            recent_bsns_year_fnnr_sttus_thstrm_ntpf      당기순이익

    Raises:
        DartUnavailable: api_key 누락 / HTTP 실패 / status 비정상.
    """
    params = {
        "corp_code": corp_code,
        "bsns_year": bsns_year,
        "reprt_code": reprt_code,
    }
    data = _dart_get(params, api_key, url=DART_OTR_CPR_INVESTMENT_URL, timeout=timeout)
    return list(data.get("list") or [])
