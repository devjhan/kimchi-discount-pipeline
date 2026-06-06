"""audit_integrity bounded context 의 외부 의존 단일 게이트 (anti-corruption layer).

``domains/catalyst/_boundary.py`` 와 isomorphic. 다른 audit_integrity 모듈은 외부
시스템 (infrastructure._common / infrastructure.kis / infrastructure.yahoo /
os.environ / file system path) 에 직접 접근하지 않고 본 모듈을 통과한다.

DART 게이트는 없음 (shadow portfolio 는 가격만 필요 — KIS/Yahoo). 통계 lib
(``stat_tests``) 과 init 템플릿 (``init_shadow_state``) 은 별도 순수 모듈로 잔존.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from infrastructure._common import utils as _utils
from infrastructure.kis import client as _kis
from infrastructure.yahoo import client as _yahoo

KST = _utils.KST

KisUnavailable = _kis.KisUnavailable
YahooUnavailable = _yahoo.YahooUnavailable


# ----------------------------------------------------------------------
# Path / time / citation
# ----------------------------------------------------------------------


def resolve_path(alias: str, *, date: str | None = None) -> Path:
    """경로 alias → Path. audit_integrity 의 경로 해석 단일 지점."""
    if alias == "operations_audit":
        return _utils.audit_dir()
    if alias == "trail_today":
        return _utils.trail_dir(date)
    if alias == "shadow_state":
        return _utils.audit_dir() / "shadow-portfolio-state.json"
    if alias == "kis_token":
        return _utils.repo_path("secrets", ".kis_token.json")
    raise KeyError(f"audit_integrity._boundary.resolve_path: unknown alias {alias!r}")


def resolve_trail_dir(date: str | None = None) -> Path:
    """오늘 (또는 지정 일자) 의 trail 디렉토리 절대경로 (= $TRAIL_TODAY)."""
    return _utils.trail_dir(date)


def now_kst() -> datetime:
    """현재 KST datetime (tz-aware)."""
    return datetime.now(KST)


def now_iso_kst() -> str:
    """현재 KST 시각의 ISO8601 표현 (citation timestamp 용)."""
    return _utils.now_iso_kst()


def normalize_to_trading_day(date: str | None) -> str:
    """``YYYY-MM-DD`` 또는 None → 가장 가까운 직전 거래일 ISO."""
    return _utils.normalize_to_trading_day(date)


def format_citation(source: str, ts: str, value: Any) -> str:
    """G7 형식 citation 문자열: ``{SOURCE}@{ISO_KST}={VALUE}``."""
    return _utils.format_citation(source, ts, value)


# ----------------------------------------------------------------------
# Env / secret / config
# ----------------------------------------------------------------------


def load_env(path: Path | str | None = None) -> dict[str, str]:
    """``.env`` 로드."""
    return _utils.load_env_file(path)


def secret_safe_log(msg: str, env: dict[str, str]) -> str:
    """env 의 secret 값을 ``***REDACTED***`` 로 치환한 메시지 반환."""
    return _utils.secret_safe_log(msg, env)


def load_thresholds() -> dict[str, Any]:
    """``governance/thresholds.yaml`` 로드 — statistics.{benchmark_tiers,shadow_portfolio}."""
    return _utils.load_yaml_config(_utils.DEFAULT_THRESHOLDS)


def thresholds_path() -> Path:
    """thresholds.yaml 절대경로 (envelope config_path 용)."""
    return Path(_utils.DEFAULT_THRESHOLDS)


def resolve_allow_yahoo_fallback(cli_value: bool | None) -> bool:
    """KIS 미가용 시 Yahoo public endpoint 사용 여부 (None 이면 behavior.yaml)."""
    return _utils.resolve_allow_yahoo_fallback(cli_value)


# ----------------------------------------------------------------------
# Output emit
# ----------------------------------------------------------------------


def write_output_safely(out_path: Path, payload: Any) -> Path:
    """G20 — 같은 경로 collision 시 ``.{N}.json`` suffix 자동 부여 후 write."""
    return _utils.write_output_safely(out_path, payload)


def base_report_envelope(
    *,
    schema: str,
    date: str,
    config_path: Path | str,
    config_version: int | str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """D-Q-2 stage envelope."""
    return _utils.base_report_envelope(
        schema=schema, date=date, config_path=config_path, config_version=config_version, extra=extra
    )


def emit_summary(stage: str, summary: dict[str, Any], out_path: Path) -> None:
    """D-Q-6 표준 stage handoff 1줄 stdout emit."""
    _utils.emit_summary_line(stage_name=stage, summary=summary, out_path=out_path)


# ----------------------------------------------------------------------
# KIS / Yahoo price — single gate (G9: 시세 read only, 주문/매매 절대 금지)
# ----------------------------------------------------------------------


def kis_has_keys(env: dict[str, str]) -> bool:
    return _kis.has_kis_keys(env)


def kis_issue_access_token(env: dict[str, str], cache_path: Path | None = None) -> str:
    return _kis.issue_access_token(env, cache_path=cache_path)


def kis_fetch_daily_ohlcv(
    *,
    token: str,
    app_key: str,
    app_secret: str,
    stock_code: str,
    period_days: int = 20,
    end_date: str | None = None,
    adjusted: bool = True,
) -> list[dict[str, Any]]:
    return _kis.fetch_daily_ohlcv(
        token=token,
        app_key=app_key,
        app_secret=app_secret,
        stock_code=stock_code,
        period_days=period_days,
        end_date=end_date,
        adjusted=adjusted,
    )


def yahoo_krx_to_yahoo(stock_code: str, market: str = "KOSPI") -> str:
    return _yahoo.krx_to_yahoo(stock_code, market)


def yahoo_fetch_daily_ohlcv(ticker: str, period_days: int = 30) -> list[dict[str, Any]]:
    return _yahoo.fetch_daily_ohlcv(ticker, period_days=period_days)
