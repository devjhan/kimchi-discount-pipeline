"""macro bounded context 의 외부 의존 단일 게이트 (anti-corruption layer).

universe / screener 의 ``_boundary.py`` 와 isomorphic 패턴. 다른 macro 모듈은
``infrastructure.*`` / ``os.environ`` / utils path helper 직접 호출 금지 — 본 모듈
통과.

export:
- Path / time / citation / env / envelope / handoff
- ``load_regimes_config`` (config/ 로더)
- FRED: ``fred_has_key``, ``fred_latest``, ``fred_series``, ``fred_history_values``,
  ``FetchError``
- Yahoo (breadth fetch): ``yahoo_fetch_daily_ohlcv``, ``yahoo_krx_to_yahoo``,
  ``YahooUnavailable``
- Breadth signal: ``load_breadth_signal`` (Stage 0a 가 작성한 yaml read)
"""
from __future__ import annotations

from datetime import date as _date
from datetime import datetime
from pathlib import Path
from typing import Any

from infrastructure._common import utils as _utils
from infrastructure.fred import client as _fred
from infrastructure.yahoo import client as _yahoo

KST = _utils.KST

# 외부 exception re-export
FetchError = _utils.FetchError
YahooUnavailable = _yahoo.YahooUnavailable


# ----------------------------------------------------------------------
# Path / time / citation
# ----------------------------------------------------------------------


def resolve_path(alias: str, *, date: str | None = None) -> Path:
    """경로 alias → Path. macro 의 경로 해석 단일 지점 (REPO_ROOT 직접)."""
    if alias == "trail_today":
        return _utils.trail_dir(date)
    if alias == "operations_audit":
        return _utils.audit_dir()
    if alias == "infra_common":
        return _utils.infra_common_dir()
    if alias == "external_signals_macro_breadth":
        return _utils.external_signals_dir() / "macro" / "breadth.yaml"
    raise KeyError(f"macro._boundary.resolve_path: unknown alias {alias!r}")


def now_kst() -> datetime:
    return datetime.now(KST)


def now_iso_kst() -> str:
    return _utils.now_iso_kst()


def is_trading_day(target: _date) -> bool:
    return _utils.is_trading_day(target.isoformat())


def normalize_to_trading_day(date_str: str | None) -> str:
    """입력 date (또는 None=오늘) 를 가장 가까운 직전 KRX 거래일로 정규화."""
    return _utils.normalize_to_trading_day(date_str)


def format_citation(source: str, ts: str, value: Any) -> str:
    return _utils.format_citation(source, ts, value)


# ----------------------------------------------------------------------
# Env / secret
# ----------------------------------------------------------------------


def load_env(path: Path | str | None = None) -> dict[str, str]:
    return _utils.load_env_file(path)


def secret_safe_log(msg: str, env: dict[str, str]) -> str:
    return _utils.secret_safe_log(msg, env)


# ----------------------------------------------------------------------
# Output emit / envelope
# ----------------------------------------------------------------------


def write_output_safely(out_path: Path, payload: Any) -> Path:
    return _utils.write_output_safely(out_path, payload)


def resolve_trail_dir(date: str | None = None) -> Path:
    return _utils.trail_dir(date)


def base_report_envelope(
    *,
    schema: str,
    date: str,
    config_path: Path | str,
    config_version: int | str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return _utils.base_report_envelope(
        schema=schema,
        date=date,
        config_path=config_path,
        config_version=config_version,
        extra=extra,
    )


def emit_summary(stage: str, summary: dict[str, Any], out_path: Path) -> None:
    _utils.emit_summary_line(stage_name=stage, summary=summary, out_path=out_path)


# ----------------------------------------------------------------------
# Config loaders — macro 내부 config/ 디렉토리 한정
# ----------------------------------------------------------------------


def _config_root() -> Path:
    return Path(__file__).resolve().parent / "config"


def load_regimes_config() -> dict[str, Any]:
    """``config/regimes.yaml`` 로드 — 4 indicator thresholds + cash_band + priority."""
    return _utils.load_yaml_config(_config_root() / "regimes.yaml")


def config_path(filename: str) -> Path:
    if "/" in filename or ".." in filename:
        raise ValueError(f"config_path: 단순 basename 만 허용 (got: {filename!r})")
    return _config_root() / filename


# ----------------------------------------------------------------------
# FRED API — single gate
# ----------------------------------------------------------------------


def fred_has_key(env: dict[str, str]) -> bool:
    return _fred.has_fred_key(env)


def fred_latest(api_key: str, series_id: str, observation_end: str) -> tuple[float, str]:
    return _fred.fred_latest(api_key, series_id, observation_end)


def fred_series(
    api_key: str,
    series_id: str,
    observation_start: str,
    observation_end: str,
) -> list[tuple[str, float]]:
    return _fred.fred_series(api_key, series_id, observation_start, observation_end)


def fred_history_values(
    api_key: str,
    series_id: str,
    observation_end: str,
    *,
    years: int = 5,
) -> list[float]:
    return _fred.fred_history_values(api_key, series_id, observation_end, years=years)


# ----------------------------------------------------------------------
# Yahoo Finance — single gate (Stage 0a breadth fetch)
# ----------------------------------------------------------------------


def yahoo_krx_to_yahoo(stock_code: str, market: str = "KOSPI") -> str:
    return _yahoo.krx_to_yahoo(stock_code, market)


def yahoo_fetch_daily_ohlcv(
    ticker: str, period_days: int = 220
) -> list[dict[str, Any]]:
    return _yahoo.fetch_daily_ohlcv(ticker, period_days=period_days)


# ----------------------------------------------------------------------
# External breadth signal (Stage 0a output, Stage 0 input)
# ----------------------------------------------------------------------


def load_breadth_signal() -> dict[str, Any]:
    """``$EXTERNAL_SIGNALS_MACRO_BREADTH_PATH`` (breadth.yaml) read."""
    return _utils.load_breadth_signal()
