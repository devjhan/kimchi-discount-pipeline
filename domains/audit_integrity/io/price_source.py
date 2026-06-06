"""가격 source — paper trade 평가용 close 조회 (KIS 우선, Yahoo fallback).

``price_for(ticker) -> (close_krw | None, G7 citation | None)``. ticker 는
``US:SPY`` / ``KR:069500`` 형식. ``date`` 시점 (또는 직전 거래일) close 를 반환한다.
모든 외부 접근은 ``_boundary`` 경유 (G9: 시세 read only — 주문/매매 절대 금지).
"""
from __future__ import annotations

from typing import Any

from domains.audit_integrity import _boundary


def _kis_close_on(rows: list[dict[str, Any]], target_yyyymmdd: str) -> float | None:
    """KIS rows 에서 target 이하 가장 최근 거래일 close."""
    best: tuple[str, float] | None = None
    for r in rows or []:
        d = (r.get("stck_bsop_date") or "").strip()
        if not d or d > target_yyyymmdd:
            continue
        try:
            c = float(str(r.get("stck_clpr") or "").replace(",", ""))
        except ValueError:
            continue
        if best is None or d > best[0]:
            best = (d, c)
    return best[1] if best else None


def _yahoo_close_on(rows: list[dict[str, Any]], target_iso: str) -> float | None:
    """Yahoo rows (date='YYYY-MM-DD') 에서 target 이하 가장 최근 close."""
    best: tuple[str, float] | None = None
    for r in rows or []:
        d = r.get("date") or ""
        if not d or d > target_iso:
            continue
        try:
            c = float(r.get("close"))
        except (TypeError, ValueError):
            continue
        if best is None or d > best[0]:
            best = (d, c)
    return best[1] if best else None


class PriceSource:
    def __init__(self, env: dict[str, str], *, date: str, allow_yahoo: bool) -> None:
        self._env = env
        self._date = date  # YYYY-MM-DD
        self._yyyymmdd = date.replace("-", "")
        self._allow_yahoo = allow_yahoo
        self._token: str | None = None
        self._token_tried = False

    def _kis_token(self) -> str | None:
        if not self._token_tried:
            self._token_tried = True
            if _boundary.kis_has_keys(self._env):
                try:
                    self._token = _boundary.kis_issue_access_token(
                        self._env, cache_path=_boundary.resolve_path("kis_token")
                    )
                except _boundary.KisUnavailable:
                    self._token = None
        return self._token

    def price_for(self, ticker: str) -> tuple[float | None, str | None]:
        market, _, code = ticker.partition(":")
        if not code:
            return None, None
        if market == "US":
            return self._yahoo(code, ticker, market="US")
        # KR — KIS 우선
        token = self._kis_token()
        if token is not None:
            try:
                rows = _boundary.kis_fetch_daily_ohlcv(
                    token=token,
                    app_key=self._env["KIS_APP_KEY"],
                    app_secret=self._env["KIS_APP_SECRET"],
                    stock_code=code,
                    period_days=20,
                    end_date=self._date,
                )
                close = _kis_close_on(rows, self._yyyymmdd)
                if close is not None:
                    return close, _boundary.format_citation(
                        "KIS", self._date, {"ticker": ticker, "close": close}
                    )
            except _boundary.KisUnavailable:
                pass
        if self._allow_yahoo:
            return self._yahoo(code, ticker, market="KOSPI")
        return None, None

    def _yahoo(self, code: str, ticker: str, *, market: str) -> tuple[float | None, str | None]:
        try:
            y_ticker = code if market == "US" else _boundary.yahoo_krx_to_yahoo(code, market)
            rows = _boundary.yahoo_fetch_daily_ohlcv(y_ticker, period_days=30)
            close = _yahoo_close_on(rows, self._date)
            if close is not None:
                return close, _boundary.format_citation(
                    "Yahoo", self._date, {"ticker": ticker, "close": close}
                )
        except _boundary.YahooUnavailable:
            pass
        return None, None
