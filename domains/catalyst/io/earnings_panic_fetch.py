"""Earnings panic fetch — 구 ``alpha_factory/stage3_earnings_panic.py`` 이전.

DART 잠정실적 발표 + 발표 전후 1일 가격 (KIS 우선, Yahoo opt-in fallback) 으로
-threshold 이상 drop 종목 검출. 구 helper 의 중간 JSON (``03-earnings-panic.json``)
은 제거 — earnings_panic detector 가 ``EarningsPanicEntry`` list 를 직접 소비.
모든 외부 접근은 ``_boundary`` 경유.

Hard guards: G6 (drop% deterministic) / G7 (가격·변화율 source citation) /
G8 (가격 미가용 시 entry skip + warning, hallucination 금지) / G21 (KIS secret 미노출).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from domains.catalyst import _boundary

# 어닝 발표 키워드 (DART pblntf_ty='I' / 'E')
ANNOUNCEMENT_KEYWORDS = (
    "잠정실적",
    "영업(잠정)실적",
    "영업잠정실적",
    "매출액또는손익구조",
    "매출액또는손익구조30%",
)


@dataclass
class EarningsAnnouncement:
    ticker: str
    name: str
    rcept_no: str
    rcept_dt: str  # YYYYMMDD
    report_nm: str


@dataclass
class EarningsPanicEntry:
    ticker: str
    name: str
    rcept_no: str
    rcept_dt: str
    report_nm: str
    price_d_minus_1: float | None
    price_d_plus_1: float | None
    one_day_drop_pct: float | None
    threshold: float
    triggered: bool
    price_source: str  # 'KIS' | 'Yahoo' | 'unavailable'
    citations: list[str] = field(default_factory=list)
    skip_reason: str | None = None


def discover_earnings_announcements(
    env: dict[str, str],
    *,
    end_date: str,
    lookback_days: int,
    universe_codes: set[str],
) -> tuple[list[EarningsAnnouncement], list[str]]:
    """DART pblntf_ty='I' / 'E' lookback 으로 어닝 발표 검출."""
    warnings: list[str] = []
    if not _boundary.dart_has_key(env):
        warnings.append("DART_API_KEY missing → earnings_panic 어닝 발표 ingest skipped")
        return [], warnings

    api_key = env["DART_API_KEY"]
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    bgn_dt = end_dt - timedelta(days=lookback_days)

    out: list[EarningsAnnouncement] = []
    seen: set[str] = set()
    try:
        for pblntf in ("I", "E"):
            for item in _boundary.dart_iter_disclosures(
                api_key,
                bgn_de=bgn_dt.strftime("%Y-%m-%d"),
                end_de=end_date,
                pblntf_ty=pblntf,
            ):
                report_nm = (item.get("report_nm") or "").strip()
                if not any(k in report_nm for k in ANNOUNCEMENT_KEYWORDS):
                    continue
                stock_code = (item.get("stock_code") or "").strip()
                if not stock_code or stock_code not in universe_codes:
                    continue
                rcept_no = (item.get("rcept_no") or "").strip()
                rcept_dt = (item.get("rcept_dt") or "").strip()
                if not rcept_dt:
                    continue
                key = f"{stock_code}|{rcept_no}"
                if key in seen:
                    continue
                seen.add(key)
                out.append(
                    EarningsAnnouncement(
                        ticker=f"KR:{stock_code}",
                        name=(item.get("corp_name") or "").strip(),
                        rcept_no=rcept_no,
                        rcept_dt=rcept_dt,
                        report_nm=report_nm,
                    )
                )
    except _boundary.DartUnavailable as exc:
        warnings.append(f"DART earnings ingest fail: {exc}")
    return out, warnings


# ----------------------------------------------------------------------
# 가격 fetch — KIS 우선, Yahoo fallback
# ----------------------------------------------------------------------


def _kis_daily_window(
    *, env: dict[str, str], stock_code: str, end_date: str
) -> tuple[list[dict[str, Any]] | None, str | None]:
    """KIS 일봉 조회. (rows, error_msg). rows None 이면 에러."""
    if not _boundary.kis_has_keys(env):
        return None, "KIS_APP_KEY/SECRET missing"
    cache_path = _boundary.resolve_path("kis_token")
    try:
        token = _boundary.kis_issue_access_token(env, cache_path=cache_path)
        rows = _boundary.kis_fetch_daily_ohlcv(
            token=token,
            app_key=env["KIS_APP_KEY"],
            app_secret=env["KIS_APP_SECRET"],
            stock_code=stock_code,
            period_days=20,
            end_date=end_date,
        )
        return rows, None
    except _boundary.KisUnavailable as exc:
        return None, f"KIS fail: {exc}"


def _yahoo_daily_window(
    *, stock_code: str, market: str, period_days: int = 30
) -> tuple[list[dict[str, Any]] | None, str | None]:
    """Yahoo 일봉 fallback (opt-in)."""
    try:
        ticker = _boundary.yahoo_krx_to_yahoo(stock_code, market)
        rows = _boundary.yahoo_fetch_daily_ohlcv(ticker, period_days=period_days)
        return rows, None
    except _boundary.YahooUnavailable as exc:
        return None, f"Yahoo fail: {exc}"


def _kis_around(
    rows: list[dict[str, Any]], rcept_dt: str
) -> tuple[float | None, float | None]:
    """rcept_dt (YYYYMMDD) 기준 D-1 / D+1 close. KIS rows 정렬 후 인접."""
    sorted_rows = sorted(rows or [], key=lambda r: (r.get("stck_bsop_date") or ""))
    dates = [r.get("stck_bsop_date") for r in sorted_rows]
    if rcept_dt in dates:
        i = dates.index(rcept_dt)
    else:
        i = next((idx for idx, d in enumerate(dates) if d > rcept_dt), -1)
        if i == -1:
            return None, None
    d_minus_1 = sorted_rows[i - 1] if i - 1 >= 0 else None
    d_plus_1 = sorted_rows[i + 1] if i + 1 < len(sorted_rows) else None

    def _close(r: dict[str, Any] | None) -> float | None:
        if r is None:
            return None
        try:
            return float(str(r.get("stck_clpr") or "").replace(",", ""))
        except ValueError:
            return None

    return _close(d_minus_1), _close(d_plus_1)


def _yahoo_around(
    rows: list[dict[str, Any]], rcept_dt: str
) -> tuple[float | None, float | None]:
    target_iso = f"{rcept_dt[:4]}-{rcept_dt[4:6]}-{rcept_dt[6:8]}"
    sorted_rows = sorted(rows or [], key=lambda r: r.get("date") or "")
    dates = [r.get("date") for r in sorted_rows]
    if target_iso in dates:
        i = dates.index(target_iso)
    else:
        i = next((idx for idx, d in enumerate(dates) if d > target_iso), -1)
        if i == -1:
            return None, None
    dm1 = sorted_rows[i - 1] if i - 1 >= 0 else None
    dp1 = sorted_rows[i + 1] if i + 1 < len(sorted_rows) else None

    def _close(r: dict[str, Any] | None) -> float | None:
        if r is None:
            return None
        try:
            return float(r.get("close"))
        except (TypeError, ValueError):
            return None

    return _close(dm1), _close(dp1)


def evaluate_announcement(
    ann: EarningsAnnouncement,
    *,
    env: dict[str, str],
    universe_market: dict[str, str],
    drop_threshold: float,
    allow_yahoo: bool,
    end_date: str,
    fetched_at: str,
) -> EarningsPanicEntry:
    """단일 어닝 발표 평가 — D-1/D+1 가격 fetch → drop% → triggered 판정."""
    stock_code = ann.ticker.split(":", 1)[1]
    market = universe_market.get(stock_code, "KOSPI")
    citations: list[str] = [
        _boundary.format_citation(
            "DART",
            ann.rcept_dt,
            {"rcept_no": ann.rcept_no, "type": "earnings_announcement"},
        )
    ]

    rows, kis_err = _kis_daily_window(env=env, stock_code=stock_code, end_date=end_date)
    price_source = "KIS"
    if rows is None:
        if not allow_yahoo:
            return EarningsPanicEntry(
                ticker=ann.ticker,
                name=ann.name,
                rcept_no=ann.rcept_no,
                rcept_dt=ann.rcept_dt,
                report_nm=ann.report_nm,
                price_d_minus_1=None,
                price_d_plus_1=None,
                one_day_drop_pct=None,
                threshold=drop_threshold,
                triggered=False,
                price_source="unavailable",
                citations=citations,
                skip_reason=f"price source unavailable (KIS fail, yahoo not allowed): {kis_err}",
            )
        rows, yahoo_err = _yahoo_daily_window(
            stock_code=stock_code, market=market, period_days=30
        )
        price_source = "Yahoo"
        if rows is None:
            return EarningsPanicEntry(
                ticker=ann.ticker,
                name=ann.name,
                rcept_no=ann.rcept_no,
                rcept_dt=ann.rcept_dt,
                report_nm=ann.report_nm,
                price_d_minus_1=None,
                price_d_plus_1=None,
                one_day_drop_pct=None,
                threshold=drop_threshold,
                triggered=False,
                price_source="unavailable",
                citations=citations,
                skip_reason=f"price source unavailable: KIS({kis_err}) Yahoo({yahoo_err})",
            )

    if price_source == "KIS":
        d_minus_1, d_plus_1 = _kis_around(rows, ann.rcept_dt)
    else:
        d_minus_1, d_plus_1 = _yahoo_around(rows, ann.rcept_dt)

    drop_pct: float | None = None
    triggered = False
    if d_minus_1 and d_plus_1 and d_minus_1 > 0:
        drop_pct = round((d_plus_1 / d_minus_1) - 1.0, 4)
        triggered = drop_pct <= drop_threshold

    citations.append(
        _boundary.format_citation(
            price_source,
            fetched_at,
            {
                "stock_code": stock_code,
                "d_minus_1": d_minus_1,
                "d_plus_1": d_plus_1,
                "drop_pct": drop_pct,
            },
        )
    )

    return EarningsPanicEntry(
        ticker=ann.ticker,
        name=ann.name,
        rcept_no=ann.rcept_no,
        rcept_dt=ann.rcept_dt,
        report_nm=ann.report_nm,
        price_d_minus_1=d_minus_1,
        price_d_plus_1=d_plus_1,
        one_day_drop_pct=drop_pct,
        threshold=drop_threshold,
        triggered=triggered,
        price_source=price_source,
        citations=citations,
        skip_reason=None if (d_minus_1 and d_plus_1) else "missing D-1 or D+1 close",
    )
