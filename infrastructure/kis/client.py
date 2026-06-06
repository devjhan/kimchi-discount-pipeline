"""
infrastructure/kis/client.py — 한국투자증권 OpenAPI minimal client.

Stage 1 (preferred share spread, NAV calc 자회사 시총), Stage 3 (earnings panic
가격 join) 의 가격 데이터 source. 추가로 사용자 결정 (2026-05-09) 에 따라
**계좌 read-only 조회** (잔고 / 실현손익 / 일별 체결 / 매수가능 / 매도가능수량 /
계좌자산 6 endpoint) 가 whitelist 한정으로 활성화되었다.

본 module 의 KIS API 사용은 다음 3중으로 매매/주문을 차단한다 (G9b/G9c):
    1) 코드 부재 — 본 module 상단 `PATH_*` 상수에 매매/주문 endpoint path 문자열
                   부재. 추가 금지.
    2) Bash deny  — `.claude/settings.json` 의 `*kis_order*`, `*place_order*`,
                   write TR_ID literal (TTTC080[123]U / TTTC0851U / CTSC0008U) 거부
    3) Policy whitelist — `governance/runtime-policy.yaml` 의
                   `kis.read_only_account.allowed_tr_ids` 에 없는 tr_id 호출 시
                   `KisUnavailable` raise. `forbidden_tr_ids` 명시 호출은 즉시
                   `KisAutoTradeBlocked` raise (서로 다른 예외로 audit 분리).

Hard guards (governance/specs/hard-guards.md):
    - G7: 모든 가격 / 시총 / 잔고 숫자에 source citation (KIS@{yyyymmdd_hhmm}={value})
    - G8: token issue / fetch 실패 시 KisUnavailable raise — caller graceful skip
    - G9a: 자동 매매 체결 절대 금지
    - G9b: read-only 계좌 조회는 allowed_tr_ids whitelist 한정
    - G9c: 매매/주문 endpoint 3중 차단 (위)
    - G21: KIS_APP_KEY / KIS_APP_SECRET / KIS_ACCOUNT_NUMBER stdout/log 노출 금지
           (caller 의 secret_safe_log 적용 — KIS_ACCOUNT_NUMBER 는 이미
           SECRET_ENV_KEYS 에 등록됨)

Token cache: secrets/.kis_token.json, TTL 23h, 만료 시 재발급.
"""

from __future__ import annotations

import json
import random
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from infrastructure._common.utils import FetchError, safe_http_json

# real-account base URL only (사용자 결정).
REAL_BASE_URL = "https://openapi.koreainvestment.com:9443"

# Token TTL — KIS 정책상 24h. 1h 마진을 두고 23h 사용.
TOKEN_TTL_SECONDS = 23 * 3600

# 시세 endpoints (read-only quote)
PATH_OAUTH_TOKEN = "/oauth2/tokenP"
PATH_INQUIRE_PRICE = "/uapi/domestic-stock/v1/quotations/inquire-price"
PATH_INQUIRE_DAILY_OHLCV = (
    "/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice"
)

# 계좌 read-only endpoints (G9b — allowed_tr_ids 와 1:1 매핑)
PATH_ACCOUNT_BALANCE = "/uapi/domestic-stock/v1/trading/inquire-balance"
PATH_BALANCE_REALIZED_PNL = "/uapi/domestic-stock/v1/trading/inquire-balance-rlz-pl"
PATH_DAILY_EXECUTIONS = "/uapi/domestic-stock/v1/trading/inquire-daily-ccld"
PATH_BUYABLE_AMOUNT = "/uapi/domestic-stock/v1/trading/inquire-psbl-order"
PATH_SELLABLE_QTY = "/uapi/domestic-stock/v1/trading/inquire-psbl-sell"
PATH_ACCOUNT_ASSETS = "/uapi/domestic-stock/v1/trading/inquire-account-balance"

# TR_ID — 시세 호출 식별자
TR_ID_INQUIRE_PRICE = "FHKST01010100"
TR_ID_INQUIRE_DAILY_OHLCV = "FHKST03010100"

# TR_ID — 계좌 read-only (반드시 governance/runtime-policy.yaml 의
# kis.read_only_account.allowed_tr_ids 와 동일 set 유지. 추가 시 양쪽 동시 갱신.)
TR_ID_ACCOUNT_BALANCE = "TTTC8434R"
TR_ID_BALANCE_REALIZED_PNL = "TTTC8494R"
TR_ID_DAILY_EXECUTIONS_RECENT = "TTTC0081R"   # 3개월 이내
TR_ID_DAILY_EXECUTIONS_OLDER = "CTSC9215R"    # 3개월 이전
TR_ID_BUYABLE_AMOUNT = "TTTC8908R"
TR_ID_SELLABLE_QTY = "TTTC8408R"
TR_ID_ACCOUNT_ASSETS = "CTRP6548R"

# 시장 분류 코드
FID_COND_MRKT_DIV_CODE = "J"  # J=KRX 주식


class KisUnavailable(RuntimeError):
    """KIS API 미사용 가능 (key 없음 / token 발급 실패 / HTTP). caller graceful skip 강제."""


class KisAutoTradeBlocked(RuntimeError):
    """G9c — 매매/주문 TR_ID 호출이 명시 차단되었다 (audit 분리용 별도 예외).

    `KisUnavailable` 와 다른 점은 caller 가 graceful skip 이 아닌 **즉시 작업 중단 +
    사용자 보고** 해야 한다는 신호. 본 예외 raise 자체가 audit-process 의 룰 위반
    finding 이 된다.
    """


# ============================================================
# Key / token helpers
# ============================================================


def has_kis_keys(env: dict[str, str]) -> bool:
    """편의 함수 — caller 가 graceful skip 분기 결정 시."""
    return bool(
        env.get("KIS_APP_KEY", "").strip()
        and env.get("KIS_APP_SECRET", "").strip()
    )


# Retry-on HTTP status codes for KIS POST (oauth tokenP 일시적 장애).
# 401/403 은 key 문제이므로 retry 안 함 (무한 재시도 방지).
_KIS_POST_RETRY_STATUS: tuple[int, ...] = (408, 429, 500, 502, 503, 504)


def _is_transient_kis_error(exc: Exception) -> bool:
    """urlopen socket timeout 판별 — KIS oauth endpoint 가 종종 timeout 한다."""
    if isinstance(exc, socket.timeout):
        return True
    if isinstance(exc, urllib.error.URLError):
        reason = getattr(exc, "reason", None)
        if isinstance(reason, socket.timeout):
            return True
        if isinstance(reason, str) and "time" in reason.lower():
            return True
    return False


def _post_json(
    url: str,
    payload: dict[str, Any],
    *,
    headers: dict[str, str] | None = None,
    timeout: float = 10.0,
    retry: int = 0,
    backoff_base: float = 1.0,
) -> dict[str, Any]:
    """POST + JSON body. KIS oauth tokenP 용. 실패 시 FetchError raise.

    retry>0 시 5xx/429/408/timeout 만 exponential backoff 으로 재시도.
    401/403 (key 문제) 은 즉시 fail — 잘못된 key 무한 재시도 방지.
    """
    body = json.dumps(payload).encode("utf-8")
    hdr = {
        "Content-Type": "application/json; charset=utf-8",
        "User-Agent": "investment-pipeline/1.0",
    }
    if headers:
        hdr.update(headers)
    req = urllib.request.Request(url, data=body, headers=hdr, method="POST")
    raw: str | None = None
    last_exc: Exception | None = None
    for attempt in range(retry + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8")
            break
        except urllib.error.HTTPError as exc:
            last_exc = exc
            if exc.code in _KIS_POST_RETRY_STATUS and attempt < retry:
                time.sleep(backoff_base * (2 ** attempt) + random.uniform(0, 0.5))
                continue
            raise FetchError(f"KIS POST fail: {url} — {exc}") from exc
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if _is_transient_kis_error(exc) and attempt < retry:
                time.sleep(backoff_base * (2 ** attempt) + random.uniform(0, 0.5))
                continue
            raise FetchError(f"KIS POST fail: {url} — {exc}") from exc
    if raw is None:
        # 방어 — loop 가 raise 또는 break. 도달 불가.
        raise FetchError(f"KIS POST fail: {url} — {last_exc}")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise FetchError(
            f"KIS POST JSON parse fail: {url} — first 200 chars: {raw[:200]!r}"
        ) from exc


def issue_access_token(
    env: dict[str, str],
    *,
    cache_path: Path | None = None,
    base_url: str = REAL_BASE_URL,
) -> str:
    """
    KIS OAuth2 access token 발급. cache hit (TTL 23h 이내) 시 재사용.

    Args:
        env: load_env_file() 결과. KIS_APP_KEY / KIS_APP_SECRET 필요.
        cache_path: token cache JSON 경로. None 이면 cache 미사용 (매번 재발급).
        base_url: real-account base URL.

    Raises:
        KisUnavailable: key 미설정 / token 발급 실패.
    """
    if not has_kis_keys(env):
        raise KisUnavailable("KIS_APP_KEY / KIS_APP_SECRET missing")

    # Cache hit?
    if cache_path is not None and cache_path.exists():
        try:
            with cache_path.open("r", encoding="utf-8") as f:
                cached = json.load(f)
            issued_at = int(cached.get("issued_at_epoch", 0))
            ttl = int(cached.get("ttl_seconds", TOKEN_TTL_SECONDS))
            if issued_at and (time.time() - issued_at) < ttl:
                tok = cached.get("access_token")
                if tok:
                    return str(tok)
        except Exception:  # noqa: BLE001 — corrupted cache → re-issue
            pass

    payload = {
        "grant_type": "client_credentials",
        "appkey": env["KIS_APP_KEY"],
        "appsecret": env["KIS_APP_SECRET"],
    }
    try:
        # retry=2 + backoff_base=2.0 → worst-case wait 1+2 ≈ 3 초.
        # 23h token cache 가 한 번 채워지면 다음 cron 까지 KIS 안정성에 영향 미미.
        data = _post_json(
            f"{base_url}{PATH_OAUTH_TOKEN}",
            payload,
            retry=2,
            backoff_base=2.0,
        )
    except FetchError as exc:
        raise KisUnavailable(f"token issue fail: {exc}") from exc
    token = data.get("access_token")
    if not token:
        raise KisUnavailable(
            f"token issue: response missing access_token (msg={data.get('msg1')!r})"
        )

    # Cache write
    if cache_path is not None:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        out = {
            "issued_at_epoch": int(time.time()),
            "ttl_seconds": TOKEN_TTL_SECONDS,
            "access_token": token,
            # token_type / expires_in 도 보관 — 디버깅 용도, secret 아님 (token 자체가 secret)
            "token_type": data.get("token_type"),
            "expires_in": data.get("expires_in"),
        }
        tmp = cache_path.with_suffix(cache_path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False)
        tmp.replace(cache_path)
        # 권한 600 (best-effort — secret 보호)
        try:
            cache_path.chmod(0o600)
        except OSError:
            pass

    return str(token)


# ============================================================
# Read-only quote endpoints
# ============================================================


def _kis_get(
    base_url: str,
    path: str,
    params: dict[str, Any],
    *,
    token: str,
    app_key: str,
    app_secret: str,
    tr_id: str,
    timeout: float = 10.0,
) -> dict[str, Any]:
    """KIS GET wrapper. rt_cd != '0' 이면 KisUnavailable raise."""
    full_url = f"{base_url}{path}?{urllib.parse.urlencode(params)}"
    headers = {
        "Authorization": f"Bearer {token}",
        "appkey": app_key,
        "appsecret": app_secret,
        "tr_id": tr_id,
        "User-Agent": "investment-pipeline/1.0",
    }
    try:
        data = safe_http_json(full_url, headers=headers, timeout=timeout)
    except FetchError as exc:
        raise KisUnavailable(f"KIS GET fail: {path} — {exc}") from exc
    rt_cd = data.get("rt_cd")
    if rt_cd not in (None, "0"):
        raise KisUnavailable(
            f"KIS rt_cd={rt_cd} msg={data.get('msg1')!r} path={path}"
        )
    return data


def fetch_current_price(
    *,
    token: str,
    app_key: str,
    app_secret: str,
    stock_code: str,
    base_url: str = REAL_BASE_URL,
) -> dict[str, Any]:
    """
    현재가 조회.

    Args:
        stock_code: 6자리 KRX 종목 코드 (예: '005930').

    Returns:
        KIS 응답 `output` 필드 (현재가 / 전일대비 / 시총 등 dict).

    Raises:
        KisUnavailable: HTTP / rt_cd 비정상.
    """
    if len(stock_code) != 6 or not stock_code.isdigit():
        raise KisUnavailable(f"invalid stock_code={stock_code!r}")
    params = {
        "FID_COND_MRKT_DIV_CODE": FID_COND_MRKT_DIV_CODE,
        "FID_INPUT_ISCD": stock_code,
    }
    data = _kis_get(
        base_url,
        PATH_INQUIRE_PRICE,
        params,
        token=token,
        app_key=app_key,
        app_secret=app_secret,
        tr_id=TR_ID_INQUIRE_PRICE,
    )
    return dict(data.get("output") or {})


def fetch_daily_ohlcv(
    *,
    token: str,
    app_key: str,
    app_secret: str,
    stock_code: str,
    period_days: int = 100,
    end_date: str | None = None,
    adjusted: bool = True,
    base_url: str = REAL_BASE_URL,
) -> list[dict[str, Any]]:
    """
    일봉 시세 조회 (최대 100일 / 1회).

    Args:
        stock_code: 6자리.
        period_days: 100 hard cap (KIS 한도). 더 긴 기간은 caller 가 분할 호출.
        end_date: 'YYYYMMDD' 또는 'YYYY-MM-DD'. None=최근.
        adjusted: True=수정주가, False=원주가.

    Returns:
        list of dict (output2 — 일별 OHLCV row).

    Raises:
        KisUnavailable.
    """
    if len(stock_code) != 6 or not stock_code.isdigit():
        raise KisUnavailable(f"invalid stock_code={stock_code!r}")
    if period_days <= 0 or period_days > 100:
        raise KisUnavailable(f"period_days out of range: {period_days}")
    params: dict[str, Any] = {
        "FID_COND_MRKT_DIV_CODE": FID_COND_MRKT_DIV_CODE,
        "FID_INPUT_ISCD": stock_code,
        "FID_PERIOD_DIV_CODE": "D",  # D=일봉
        "FID_ORG_ADJ_PRC": "0" if adjusted else "1",  # 0=수정주가
    }
    if end_date:
        params["FID_INPUT_DATE_2"] = end_date.replace("-", "")
    data = _kis_get(
        base_url,
        PATH_INQUIRE_DAILY_OHLCV,
        params,
        token=token,
        app_key=app_key,
        app_secret=app_secret,
        tr_id=TR_ID_INQUIRE_DAILY_OHLCV,
    )
    rows = data.get("output2") or []
    return [dict(r) for r in rows[:period_days]]


# ============================================================
# Read-only account endpoints  (G9b — whitelist 한정)
# ============================================================


def _load_read_only_policy() -> dict[str, Any]:
    """`governance/runtime-policy.yaml` (+local override) 의 kis.read_only_account 섹션 read.

    미존재 시 `{enabled: False, allowed_tr_ids: [], forbidden_tr_ids: []}` default —
    안전 기본값 (계좌 호출 차단).
    """
    # late import — utils 가 이 module 을 import 하지 않으므로 cycle 없음
    from infrastructure._common.utils import load_runtime_policy

    policy = load_runtime_policy()
    section = (policy.get("kis") or {}).get("read_only_account") or {}
    return {
        "enabled": bool(section.get("enabled", False)),
        "allowed_tr_ids": tuple(section.get("allowed_tr_ids") or ()),
        "forbidden_tr_ids": tuple(section.get("forbidden_tr_ids") or ()),
    }


def _enforce_read_only_policy(tr_id: str) -> None:
    """G9b/c — tr_id 호출 전 정책 검사. 위반 시 즉시 raise.

    - forbidden_tr_ids 명시 호출 → KisAutoTradeBlocked (severity: highest)
    - read_only_account.enabled=False → KisUnavailable (caller graceful skip)
    - allowed_tr_ids whitelist 외 → KisUnavailable
    """
    policy = _load_read_only_policy()
    if tr_id in policy["forbidden_tr_ids"]:
        # G9c hard violation. 절대 진행 금지.
        raise KisAutoTradeBlocked(
            f"tr_id={tr_id!r} is in kis.read_only_account.forbidden_tr_ids "
            f"(매매/주문 endpoint 호출 차단)"
        )
    if not policy["enabled"]:
        raise KisUnavailable(
            "kis.read_only_account.enabled=False — runtime-policy.local.yaml 에서 "
            "kis.read_only_account.enabled: true 로 override 해야 활성"
        )
    if tr_id not in policy["allowed_tr_ids"]:
        raise KisUnavailable(
            f"tr_id={tr_id!r} not in kis.read_only_account.allowed_tr_ids "
            f"(whitelist 외 호출 거부)"
        )


def _split_account_number(env: dict[str, str]) -> tuple[str, str]:
    """KIS_ACCOUNT_NUMBER (`12345678-01`) 를 CANO + ACNT_PRDT_CD 로 분해.

    - 형식: 8자리 숫자 + '-' + 2자리 숫자
    - 미설정 / 형식 위반 시 KisUnavailable raise (caller graceful skip)
    """
    raw = (env.get("KIS_ACCOUNT_NUMBER") or "").strip()
    if not raw:
        raise KisUnavailable("KIS_ACCOUNT_NUMBER missing")
    parts = raw.split("-")
    if len(parts) != 2 or not parts[0].isdigit() or not parts[1].isdigit():
        raise KisUnavailable(
            "KIS_ACCOUNT_NUMBER format invalid (expected 8자리-2자리, got redacted len="
            f"{len(raw)})"
        )
    cano, prdt = parts[0], parts[1]
    if len(cano) != 8 or len(prdt) != 2:
        raise KisUnavailable("KIS_ACCOUNT_NUMBER digits invalid")
    return cano, prdt


def fetch_account_balance(
    *,
    token: str,
    app_key: str,
    app_secret: str,
    account_number: str,
    base_url: str = REAL_BASE_URL,
) -> dict[str, Any]:
    """주식잔고조회 (TTTC8434R) — 보유 종목 + 평가금액.

    Args:
        account_number: '12345678-01' 형식 (CANO-ACNT_PRDT_CD).

    Returns:
        dict with keys 'positions' (list of holding dict), 'summary' (총평가/매입/PnL).
    """
    _enforce_read_only_policy(TR_ID_ACCOUNT_BALANCE)
    cano, prdt = _split_account_number({"KIS_ACCOUNT_NUMBER": account_number})
    params = {
        "CANO": cano,
        "ACNT_PRDT_CD": prdt,
        "AFHR_FLPR_YN": "N",
        "OFL_YN": "",
        "INQR_DVSN": "02",       # 02=종목별
        "UNPR_DVSN": "01",
        "FUND_STTL_ICLD_YN": "N",
        "FNCG_AMT_AUTO_RDPT_YN": "N",
        "PRCS_DVSN": "01",       # 01=전일매매포함
        "CTX_AREA_FK100": "",
        "CTX_AREA_NK100": "",
    }
    data = _kis_get(
        base_url,
        PATH_ACCOUNT_BALANCE,
        params,
        token=token,
        app_key=app_key,
        app_secret=app_secret,
        tr_id=TR_ID_ACCOUNT_BALANCE,
    )
    return {
        "positions": [dict(r) for r in (data.get("output1") or [])],
        "summary": [dict(r) for r in (data.get("output2") or [])],
    }


def fetch_realized_pnl(
    *,
    token: str,
    app_key: str,
    app_secret: str,
    account_number: str,
    base_url: str = REAL_BASE_URL,
) -> dict[str, Any]:
    """주식잔고조회_실현손익 (TTTC8494R) — 종목별 실현 손익."""
    _enforce_read_only_policy(TR_ID_BALANCE_REALIZED_PNL)
    cano, prdt = _split_account_number({"KIS_ACCOUNT_NUMBER": account_number})
    params = {
        "CANO": cano,
        "ACNT_PRDT_CD": prdt,
        "AFHR_FLPR_YN": "N",
        "OFL_YN": "",
        "INQR_DVSN": "00",
        "UNPR_DVSN": "01",
        "FUND_STTL_ICLD_YN": "N",
        "FNCG_AMT_AUTO_RDPT_YN": "N",
        "PRCS_DVSN": "00",
        "COST_ICLD_YN": "N",
        "CTX_AREA_FK100": "",
        "CTX_AREA_NK100": "",
    }
    data = _kis_get(
        base_url,
        PATH_BALANCE_REALIZED_PNL,
        params,
        token=token,
        app_key=app_key,
        app_secret=app_secret,
        tr_id=TR_ID_BALANCE_REALIZED_PNL,
    )
    return {
        "positions": [dict(r) for r in (data.get("output1") or [])],
        "summary": [dict(r) for r in (data.get("output2") or [])],
    }


def fetch_daily_executions(
    *,
    token: str,
    app_key: str,
    app_secret: str,
    account_number: str,
    start_date: str,
    end_date: str,
    base_url: str = REAL_BASE_URL,
) -> list[dict[str, Any]]:
    """주식일별주문체결조회 (TTTC0081R / CTSC9215R 분기) — 일별 주문/체결 내역.

    Args:
        start_date / end_date: 'YYYYMMDD' 또는 'YYYY-MM-DD'.
            end_date 가 90일 이상 과거이면 CTSC9215R 사용.

    Returns:
        list of execution row dict.
    """
    import datetime as _dt

    end_clean = end_date.replace("-", "")
    start_clean = start_date.replace("-", "")
    today = _dt.date.today()
    end_dt = _dt.date(int(end_clean[:4]), int(end_clean[4:6]), int(end_clean[6:8]))
    use_older = (today - end_dt).days >= 90
    tr_id = TR_ID_DAILY_EXECUTIONS_OLDER if use_older else TR_ID_DAILY_EXECUTIONS_RECENT

    _enforce_read_only_policy(tr_id)
    cano, prdt = _split_account_number({"KIS_ACCOUNT_NUMBER": account_number})
    params = {
        "CANO": cano,
        "ACNT_PRDT_CD": prdt,
        "INQR_STRT_DT": start_clean,
        "INQR_END_DT": end_clean,
        "SLL_BUY_DVSN_CD": "00",   # 00=전체, 01=매도, 02=매수
        "INQR_DVSN": "00",
        "PDNO": "",
        "CCLD_DVSN": "00",         # 00=전체
        "ORD_GNO_BRNO": "",
        "ODNO": "",
        "INQR_DVSN_3": "00",
        "INQR_DVSN_1": "",
        "CTX_AREA_FK100": "",
        "CTX_AREA_NK100": "",
    }
    data = _kis_get(
        base_url,
        PATH_DAILY_EXECUTIONS,
        params,
        token=token,
        app_key=app_key,
        app_secret=app_secret,
        tr_id=tr_id,
    )
    return [dict(r) for r in (data.get("output1") or [])]


def fetch_buyable_amount(
    *,
    token: str,
    app_key: str,
    app_secret: str,
    account_number: str,
    stock_code: str = "",
    base_url: str = REAL_BASE_URL,
) -> dict[str, Any]:
    """매수가능조회 (TTTC8908R) — 종목별 매수 가능 수량/금액.

    Args:
        stock_code: 6자리 종목 코드. 빈 문자열이면 종목 무관 현금성 가능액.
    """
    _enforce_read_only_policy(TR_ID_BUYABLE_AMOUNT)
    cano, prdt = _split_account_number({"KIS_ACCOUNT_NUMBER": account_number})
    if stock_code and (len(stock_code) != 6 or not stock_code.isdigit()):
        raise KisUnavailable(f"invalid stock_code={stock_code!r}")
    params = {
        "CANO": cano,
        "ACNT_PRDT_CD": prdt,
        "PDNO": stock_code,
        "ORD_UNPR": "0",
        "ORD_DVSN": "01",          # 01=시장가
        "CMA_EVLU_AMT_ICLD_YN": "N",
        "OVRS_ICLD_YN": "N",
    }
    data = _kis_get(
        base_url,
        PATH_BUYABLE_AMOUNT,
        params,
        token=token,
        app_key=app_key,
        app_secret=app_secret,
        tr_id=TR_ID_BUYABLE_AMOUNT,
    )
    return dict(data.get("output") or {})


def fetch_sellable_qty(
    *,
    token: str,
    app_key: str,
    app_secret: str,
    account_number: str,
    stock_code: str,
    base_url: str = REAL_BASE_URL,
) -> dict[str, Any]:
    """매도가능수량조회 (TTTC8408R) — 종목별 매도 가능 수량."""
    _enforce_read_only_policy(TR_ID_SELLABLE_QTY)
    if len(stock_code) != 6 or not stock_code.isdigit():
        raise KisUnavailable(f"invalid stock_code={stock_code!r}")
    cano, prdt = _split_account_number({"KIS_ACCOUNT_NUMBER": account_number})
    params = {
        "CANO": cano,
        "ACNT_PRDT_CD": prdt,
        "PDNO": stock_code,
    }
    data = _kis_get(
        base_url,
        PATH_SELLABLE_QTY,
        params,
        token=token,
        app_key=app_key,
        app_secret=app_secret,
        tr_id=TR_ID_SELLABLE_QTY,
    )
    return dict(data.get("output") or {})


def fetch_account_assets(
    *,
    token: str,
    app_key: str,
    app_secret: str,
    account_number: str,
    base_url: str = REAL_BASE_URL,
) -> dict[str, Any]:
    """투자계좌자산현황조회 (CTRP6548R) — 계좌 총자산 / 순자산 / 평가금액 종합."""
    _enforce_read_only_policy(TR_ID_ACCOUNT_ASSETS)
    cano, prdt = _split_account_number({"KIS_ACCOUNT_NUMBER": account_number})
    params = {
        "CANO": cano,
        "ACNT_PRDT_CD": prdt,
        "INQR_DVSN_1": "",
        "BSPR_BF_DT_APLY_YN": "",
    }
    data = _kis_get(
        base_url,
        PATH_ACCOUNT_ASSETS,
        params,
        token=token,
        app_key=app_key,
        app_secret=app_secret,
        tr_id=TR_ID_ACCOUNT_ASSETS,
    )
    return {
        "by_currency": [dict(r) for r in (data.get("output1") or [])],
        "totals": dict(data.get("output2") or {}),
    }


__all__ = [
    "REAL_BASE_URL",
    "KisUnavailable",
    "KisAutoTradeBlocked",
    "has_kis_keys",
    "issue_access_token",
    "fetch_current_price",
    "fetch_daily_ohlcv",
    # G9b — read-only account
    "fetch_account_balance",
    "fetch_realized_pnl",
    "fetch_daily_executions",
    "fetch_buyable_amount",
    "fetch_sellable_qty",
    "fetch_account_assets",
]
