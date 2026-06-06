"""
infrastructure/yahoo/client.py — Yahoo Finance public chart endpoint (KIS fallback).

KIS API 미가용 환경에서 한국 종목 일봉 OHLCV 를 가져오기 위한 minimal client.
**opt-in fallback** — caller 가 명시적 `--allow-yahoo-fallback` 시에만 사용.

본 source 는 한국 종목 데이터의 quality / delay 이슈가 있을 수 있으나,
secret 불필요 + dependency-free 라 KIS 미가용 환경에서도 day-1 운용을
완전 막지 않기 위한 boundary helper.

Hard guards:
    - G7: 모든 가져온 가격에 source citation (Yahoo@{ts}={value})
    - G8: HTTP 4xx/5xx → YahooUnavailable raise (caller graceful skip)
    - secret 불필요 — G21 비-적용
"""

from __future__ import annotations

import time
from typing import Any

from infrastructure._common.utils import FetchError, safe_http_json

YAHOO_CHART_BASE = "https://query1.finance.yahoo.com/v8/finance/chart"

# KRX market 분류 → Yahoo suffix
MARKET_SUFFIX = {
    "KOSPI": "KS",
    "KOSDAQ": "KQ",
}


class YahooUnavailable(RuntimeError):
    """Yahoo public endpoint 응답 비정상. caller graceful skip 강제."""


def krx_to_yahoo(stock_code: str, market: str = "KOSPI") -> str:
    """
    6자리 KRX 종목 코드 + 시장 → Yahoo ticker.

    예: 005930 + KOSPI → 005930.KS
        035420 + KOSDAQ → 035420.KQ
    """
    if len(stock_code) != 6 or not stock_code.isdigit():
        raise YahooUnavailable(f"invalid stock_code={stock_code!r}")
    market = market.upper()
    if market not in MARKET_SUFFIX:
        raise YahooUnavailable(f"unknown market={market!r} (allowed: KOSPI, KOSDAQ)")
    return f"{stock_code}.{MARKET_SUFFIX[market]}"


def fetch_daily_ohlcv(
    yahoo_ticker: str,
    *,
    period_days: int = 365,
    timeout: float = 10.0,
) -> list[dict[str, Any]]:
    """
    Yahoo public chart endpoint 으로 일봉 OHLCV fetch.

    Args:
        yahoo_ticker: 'XXXXXX.KS' / 'XXXXXX.KQ' 식.
        period_days: lookback 일수 (period1 = now - days * 86400).

    Returns:
        list of dict with keys:
            date (YYYY-MM-DD), timestamp, open, high, low, close, volume.
        결측 row 는 skip.

    Raises:
        YahooUnavailable: HTTP 실패 / 응답 schema 비정상.
    """
    if period_days <= 0 or period_days > 5 * 365:
        raise YahooUnavailable(f"period_days out of range: {period_days}")
    now = int(time.time())
    period1 = now - period_days * 86400
    params = {
        "period1": period1,
        "period2": now,
        "interval": "1d",
        "includePrePost": "false",
        "events": "div,splits",
    }
    url = f"{YAHOO_CHART_BASE}/{yahoo_ticker}"
    try:
        data = safe_http_json(url, params=params, timeout=timeout)
    except FetchError as exc:
        raise YahooUnavailable(f"Yahoo fetch fail: {yahoo_ticker} — {exc}") from exc

    chart = (data.get("chart") or {})
    err = chart.get("error")
    if err:
        raise YahooUnavailable(
            f"Yahoo chart error: {yahoo_ticker} — {err}"
        )
    results = chart.get("result") or []
    if not results:
        raise YahooUnavailable(f"Yahoo no result: {yahoo_ticker}")
    res = results[0]
    timestamps = res.get("timestamp") or []
    quote = ((res.get("indicators") or {}).get("quote") or [{}])[0]
    opens = quote.get("open") or []
    highs = quote.get("high") or []
    lows = quote.get("low") or []
    closes = quote.get("close") or []
    vols = quote.get("volume") or []

    out: list[dict[str, Any]] = []
    for i, ts in enumerate(timestamps):
        c = closes[i] if i < len(closes) else None
        if c is None:
            continue
        # ISO date (UTC date 충분 — daily bar)
        date_str = time.strftime("%Y-%m-%d", time.gmtime(int(ts)))
        out.append(
            {
                "date": date_str,
                "timestamp": int(ts),
                "open": opens[i] if i < len(opens) else None,
                "high": highs[i] if i < len(highs) else None,
                "low": lows[i] if i < len(lows) else None,
                "close": c,
                "volume": vols[i] if i < len(vols) else None,
            }
        )
    return out


__all__ = [
    "YAHOO_CHART_BASE",
    "MARKET_SUFFIX",
    "YahooUnavailable",
    "krx_to_yahoo",
    "fetch_daily_ohlcv",
]
