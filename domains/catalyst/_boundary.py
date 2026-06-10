"""catalyst bounded context 의 외부 의존 단일 게이트 (anti-corruption layer).

``domains/universe/_boundary.py`` 와 isomorphic. 다른 catalyst 모듈은 외부 시스템
(infrastructure._common / infrastructure.dart / infrastructure.kis /
infrastructure.yahoo / os.environ / file system path) 에 직접 접근하지 않고 본
모듈을 통과한다.

Export:
- Path / time / citation / env 기본 helper
- ``load_detectors_config`` / ``config_path`` (config/ 로더)
- ``base_report_envelope`` (D-Q-2) + ``resolve_trail_dir`` + ``emit_summary`` (D-Q-6)
  + ``resolve_allow_yahoo_fallback`` + ``normalize_to_trading_day``
- ``write_output_safely`` (G20)
- DART API: ``dart_has_key`` / ``dart_iter_disclosures`` / ``DartUnavailable``
- KIS API: ``kis_has_keys`` / ``kis_issue_access_token`` / ``kis_fetch_daily_ohlcv`` /
  ``KisUnavailable``
- Yahoo API: ``yahoo_fetch_daily_ohlcv`` / ``yahoo_krx_to_yahoo`` / ``YahooUnavailable``

새 외부 의존 추가 시 AGENTS.md 동시 갱신 의무.
"""
from __future__ import annotations

from datetime import date as _date
from datetime import datetime
from pathlib import Path
from typing import Any

from infrastructure._common import utils as _utils
from infrastructure.dart import client as _dart
from infrastructure.kis import client as _kis
from infrastructure.yahoo import client as _yahoo

KST = _utils.KST

DartUnavailable = _dart.DartUnavailable
KisUnavailable = _kis.KisUnavailable
YahooUnavailable = _yahoo.YahooUnavailable


# ----------------------------------------------------------------------
# Path / time / citation
# ----------------------------------------------------------------------


def resolve_path(alias: str, *, date: str | None = None) -> Path:
    """경로 alias → Path. catalyst 의 경로 해석 단일 지점."""
    if alias == "operations_audit":
        return _utils.audit_dir()
    if alias == "trail_today":
        return _utils.trail_dir(date)
    if alias == "nav_cache":
        # F-14: nav_history 는 재생성-불가 증거 → telemetry/nav-history (git-tracked).
        # (alias 이름은 nav_cache 로 유지 — 소비자 변경 불요, 의미만 telemetry 로 이전.)
        return _utils.nav_history_dir()
    if alias == "kis_token":
        return _utils.repo_path("secrets", ".kis_token.json")
    raise KeyError(f"catalyst._boundary.resolve_path: unknown alias {alias!r}")


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


def is_trading_day(target: _date) -> bool:
    """KRX 거래일 여부."""
    return _utils.is_trading_day(target.isoformat())


def format_citation(source: str, ts: str, value: Any) -> str:
    """G7 형식 citation 문자열: ``{SOURCE}@{ISO_KST}={VALUE}``."""
    return _utils.format_citation(source, ts, value)


# ----------------------------------------------------------------------
# Env / secret
# ----------------------------------------------------------------------


def load_env(path: Path | str | None = None) -> dict[str, str]:
    """``.env`` 로드. secret 키 포함되지만 본문/산출/stdout 노출은 secret_safe_log redact."""
    return _utils.load_env_file(path)


def secret_safe_log(msg: str, env: dict[str, str]) -> str:
    """env 의 secret 값을 ``***REDACTED***`` 로 치환한 메시지 반환."""
    return _utils.secret_safe_log(msg, env)


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
    """D-Q-2 stage envelope (schema / generated_at / date / config_path / config_version)."""
    return _utils.base_report_envelope(
        schema=schema,
        date=date,
        config_path=config_path,
        config_version=config_version,
        extra=extra,
    )


def emit_summary(stage: str, summary: dict[str, Any], out_path: Path) -> None:
    """D-Q-6 표준 stage handoff 1줄 stdout emit."""
    _utils.emit_summary_line(stage_name=stage, summary=summary, out_path=out_path)


def resolve_allow_yahoo_fallback(cli_value: bool | None) -> bool:
    """KIS 미가용 시 Yahoo public endpoint 사용 여부 (None 이면 behavior.yaml)."""
    return _utils.resolve_allow_yahoo_fallback(cli_value)


# ----------------------------------------------------------------------
# Config loaders — catalyst 내부 config/ 디렉토리 한정
# ----------------------------------------------------------------------


def _config_root() -> Path:
    return Path(__file__).resolve().parent / "config"


def load_detectors_config() -> dict[str, Any]:
    """``config/detectors.yaml`` 로드 — 활성 detector 목록 + 각 spec (threshold/lookback)."""
    return _utils.load_yaml_config(_config_root() / "detectors.yaml")


def config_path(filename: str) -> Path:
    """config 파일의 절대 경로. envelope ``config_path`` 인자 / 디버깅 용."""
    if "/" in filename or ".." in filename:
        raise ValueError(f"config_path: 단순 basename 만 허용 (got: {filename!r})")
    return _config_root() / filename


# ----------------------------------------------------------------------
# DART API — single gate
# ----------------------------------------------------------------------


def dart_has_key(env: dict[str, str]) -> bool:
    """``.env`` 의 DART_API_KEY 존재 검사 (값 자체는 노출 금지)."""
    return _dart.has_dart_key(env)


def dart_iter_disclosures(
    api_key: str,
    *,
    bgn_de: str,
    end_de: str,
    pblntf_ty: str | None = None,
    corp_code: str | None = None,
) -> Any:
    """DART /api/list.json 페이지 iter 위임. 실패 시 ``DartUnavailable`` raise."""
    return _dart.iter_disclosures(
        api_key,
        bgn_de=bgn_de,
        end_de=end_de,
        pblntf_ty=pblntf_ty,
        corp_code=corp_code,
    )


# ----------------------------------------------------------------------
# KIS API — single gate
# ----------------------------------------------------------------------


def kis_has_keys(env: dict[str, str]) -> bool:
    """``.env`` 의 KIS_APP_KEY / KIS_APP_SECRET 존재 검사."""
    return _kis.has_kis_keys(env)


def kis_issue_access_token(env: dict[str, str], cache_path: Path | None = None) -> str:
    """KIS access token 발급 (cache 파일이 valid 하면 재사용)."""
    return _kis.issue_access_token(env, cache_path=cache_path)


def kis_fetch_daily_ohlcv(
    *,
    token: str,
    app_key: str,
    app_secret: str,
    stock_code: str,
    period_days: int = 100,
    end_date: str | None = None,
    adjusted: bool = True,
) -> list[dict[str, Any]]:
    """KIS 일봉 시세 (최대 100일 / 호출)."""
    return _kis.fetch_daily_ohlcv(
        token=token,
        app_key=app_key,
        app_secret=app_secret,
        stock_code=stock_code,
        period_days=period_days,
        end_date=end_date,
        adjusted=adjusted,
    )


# ----------------------------------------------------------------------
# Yahoo Finance — single gate (KIS fallback)
# ----------------------------------------------------------------------


def yahoo_krx_to_yahoo(stock_code: str, market: str = "KOSPI") -> str:
    """KRX 6자리 stock_code → Yahoo ticker 문자열 (예: ``005930.KS``)."""
    return _yahoo.krx_to_yahoo(stock_code, market)


def yahoo_fetch_daily_ohlcv(ticker: str, period_days: int = 750) -> list[dict[str, Any]]:
    """Yahoo public chart endpoint — 일봉 fetch. 무인증."""
    return _yahoo.fetch_daily_ohlcv(ticker, period_days=period_days)
