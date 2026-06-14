"""
infrastructure/_common/utils.py — kimchi-discount-pipeline helper module.

v1 `scripts/_common.py` 의 후신. 모든 stage / domain / hook 가 공유하는 utility:
- Path helpers (REPO_ROOT 기준 직접 빌더 — operations/governance 레이아웃, env-overridable)
- env / config 로딩
- secret-safe 로깅
- 날짜 / 거래일 정규화 (KST)
- 산출물 저장 (G20 — 덮어쓰기 금지, .{N}.json suffix 보존)
- citation 포맷 (G7 — `{source}@{ts}={value}`)
- 최소 HTTP fetch (timeout / User-Agent / JSON parse)

본 module은 어떤 stage 자체 로직도 포함하지 않는다.

Hard guards (AGENTS.md Hard Guards G1-G22):
- G7: 모든 숫자 source citation 강제 — `format_citation()` 사용 권장
- G8: API fetch 실패 시 hallucination 금지 — `safe_http_json()`은 raise 하므로 caller가 graceful degrade
- G20: 산출물 덮어쓰기 금지 — `write_output_safely()` 사용 강제
- G21: secret env 변수 노출 금지 — `secret_safe_log()` + `SECRET_ENV_KEYS` enum

Path 룰: domain / hook / skill 은 본 module 의 path helper (``trail_dir`` /
``audit_dir`` / ``positions_dir`` 등) 또는 alias 환경변수를 통해 경로를 얻는다.
operations / governance 레이아웃은 본 module 에 단일 정의되며, helper 들은
env var (예: ``$TRAIL_TODAY``) 가 set 이면 우선한다 (테스트 / cron / cloud override).
"""

from __future__ import annotations

import json
import os
import random
import re
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, is_dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

# ============================================================
# Repository roots (utils.py = <repo>/infrastructure/_common/utils.py)
# ============================================================

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_THRESHOLDS = REPO_ROOT / "governance" / "thresholds.yaml"
DEFAULT_ENV = REPO_ROOT / ".env"

# ============================================================
# Timezones
# ============================================================

KST = timezone(timedelta(hours=9))
UTC = timezone.utc

# ============================================================
# Secret env keys — G21 (산출물 / 로그 / stdout 노출 금지)
# 분류 기준: API key / token / password / 계좌번호 / chat id = secret.
# 그 외 path / timezone / behavior switch / cron schedule = 비-secret.
# ============================================================

SECRET_ENV_KEYS = frozenset(
    {
        "DART_API_KEY",
        "KIS_APP_KEY",
        "KIS_APP_SECRET",
        "KIS_ACCOUNT_NUMBER",
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_CHAT_ID",
        "ALPHA_VANTAGE_API_KEY",
        "FRED_API_KEY",
    }
)


# ============================================================
# Path helpers — REPO_ROOT 기준 직접 빌더 (topology alias 미경유).
# 거래일 date 로직은 별도 (normalize_to_trading_day) — 본 helper 들은
# operations / governance / infrastructure 레이아웃을 직접 표현한다.
# env-first 의미: 테스트(conftest monkeypatch) / cron / cloud 가 디렉토리를
# tmp 로 재지정할 수 있게 env var 가 있으면 우선한다.
# ============================================================


def repo_path(*parts: str) -> Path:
    """REPO_ROOT 기준 절대경로 빌더. 흩어진 ``REPO_ROOT / "a" / "b"`` 를 대체."""
    return REPO_ROOT.joinpath(*parts)


def _env_or(repo_rel: str, env_key: str) -> Path:
    """env_key 가 set 이면 그 값, 아니면 REPO_ROOT/repo_rel 을 절대경로로 반환."""
    v = os.environ.get(env_key)
    return Path(v) if v else (REPO_ROOT / repo_rel)


def operations_day_dir(date: str | None = None) -> Path:
    """operations/{거래일} 날짜 루트 (.trails/ 의 부모). date=None → KST 오늘.

    $TRAIL_TODAY 가 set 이면 .trails/ suffix 를 제거한 부모를 반환.
    예: $TRAIL_TODAY=.../operations/2026-06-07/.trails → .../operations/2026-06-07
    """
    env = os.environ.get("TRAIL_TODAY")
    if env:
        p = Path(env)
        if p.name == ".trails":
            return p.parent
        return p
    return REPO_ROOT / "operations" / normalize_to_trading_day(date)


def trail_dir(date: str | None = None) -> Path:
    """operations/{거래일}/.trails/ — 중간 stage 산출물 저장소.

    $TRAIL_TODAY 가 set 이면 그 값 그대로 반환 (conftest / cron env-first).
    daily-brief.md 는 부모 디렉토리(operations_day_dir()) 에 산출.
    """
    env = os.environ.get("TRAIL_TODAY")
    if env:
        return Path(env)
    return REPO_ROOT / "operations" / normalize_to_trading_day(date) / ".trails"


def audit_dir() -> Path:
    # 감사/관측 증거 — 2026-06-02 operations/_audit 에서 telemetry/audit 로 이주.
    # env var 이름(AUDIT_DIR)은 테스트 monkeypatch 호환 위해 유지 (DI 이행 시 rename).
    return _env_or("telemetry/audit", "AUDIT_DIR")


def positions_dir() -> Path:
    return _env_or("telemetry/positions", "POSITIONS_DIR")


def nav_history_dir() -> Path:
    # NAV history (Σ 자회사 시총 × 지분율) = 시스템이 합성하는 재생성-불가 증거.
    # cache/ (재생성 가능, 통째 ignore) 가 아니라 telemetry/ (git-tracked cross-day
    # 증거; audit/positions 와 동류) 산하. F-14 (2026-06-04) — 오분류 교정.
    return _env_or("telemetry/nav-history", "NAV_HISTORY_DIR")


def external_signals_dir() -> Path:
    # config/signals — 사용자 입력 signal config 루트. 현재 macro breadth
    # (config/signals/macro/breadth.yaml) 전용 (재생성 가능 · 매일 overwrite ·
    # gitignored = 진성 config). agent 생성 per-ticker ingest 증거는 분리되어
    # external_signal_intake_dir() (telemetry/) 가 소유 (ADR-0008 분류축 정합).
    return _env_or("config/signals", "EXTERNAL_SIGNALS_DIR")


def external_signal_intake_dir() -> Path:
    # telemetry/external_signals — /ingest-external-signal 스킬의 per-ticker 산출
    # ({ticker}/{date}-{seq}.md). agent 생성 · 비재생성(원문 트윗/페이월 소멸 시 복구 불가)
    # · cross-day(다음 cron Stage 4 가 인용) · append-only(G20). ADR-0008 축상
    # telemetry (audit/nav-history/policy_drafts 와 동류, git-tracked 증거).
    return _env_or("telemetry/external_signals", "EXTERNAL_SIGNAL_INTAKE_DIR")


def policy_root_dir() -> Path:
    """governance/policy — 전 정책 tier 의 단일 루트 (ADR-0014)."""
    return _env_or("governance/policy", "POLICY_ROOT_DIR")


def ticker_profiles_dir() -> Path:
    """governance/policy/profiles/ticker — per-ticker(scope=ticker) 정책 (ADR-0014).

    레이아웃이 schema 의 scope 축을 미러: profiles/<scope>/<key>/v<N>.yaml.
    """
    return _env_or("governance/policy/profiles/ticker", "TICKER_PROFILES_DIR")


def segment_profiles_dir() -> Path:
    """governance/policy/profiles/segment — scope=segment 정책 (segment 가 profile_ref 로 참조).

    ADR-0014: 구 ``segment_profiles/`` 를 scope 미러 트리 ``profiles/segment/`` 로 이전.
    """
    return _env_or("governance/policy/profiles/segment", "SEGMENT_PROFILES_DIR")


def global_profiles_dir() -> Path:
    """governance/policy/profiles/global — scope=global(whole-universe) 정책 (ADR-0014).

    구 ``global/profiles/<name>.yaml`` (flat) → ``profiles/global/<name>/v<N>.yaml`` (versioned).
    cutoff *평가* 는 여전히 screener RuleFactory 소유 (스토리지 이동 ≠ 엔진 통합).
    """
    return _env_or("governance/policy/profiles/global", "GLOBAL_PROFILES_DIR")


def segments_dir() -> Path:
    """governance/policy/segments — segment 멤버십 선언 SSoT (selector + profile_ref + merge)."""
    return _env_or("governance/policy/segments", "SEGMENTS_DIR")


def concepts_dir() -> Path:
    """governance/policy/concepts — semantic concept anchor 선언 SSoT (9-a/12-a)."""
    return _env_or("governance/policy/concepts", "CONCEPTS_DIR")


def strategies_dir() -> Path:
    """governance/policy/strategies — screener strategy(profile 조합 + constants) 루트 (ADR-0014).

    구 ``global/strategies/<name>.yaml`` (flat) → ``strategies/<name>/v<N>.yaml`` (versioned).
    """
    return _env_or("governance/policy/strategies", "STRATEGIES_DIR")


def hard_guards_path() -> Path:
    """governance/policy/hard_guards.yaml — G13 catastrophic floor (singleton, flat).

    구 ``global/hard_guards.yaml`` → top-level singleton. RuleFactory 가 outer wrapper 로 소비.
    """
    base = _env_or("governance/policy", "POLICY_ROOT_DIR")
    return base / "hard_guards.yaml"


def segment_vector_store_path() -> Path:
    """telemetry/segments/vectors.sqlite — 임베딩 벡터 + scalar 선택 속성 저장소.

    벡터는 모델 버전 의존 *재생성 불가 증거* → telemetry 거주 (ADR-0008). scalar 는
    재생성 가능하나 13-a 결정대로 동일 sqlite 파일에 동거.
    """
    env = os.environ.get("SEGMENT_VECTOR_DB")
    if env:
        return Path(env)
    return REPO_ROOT / "telemetry" / "segments" / "vectors.sqlite"


def policy_drafts_dir() -> Path:
    return _env_or("telemetry/policy_drafts", "POLICY_DRAFTS_DIR")


def infra_common_dir() -> Path:
    return _env_or("infrastructure/_common", "INFRA_COMMON_DIR")


# ============================================================
# Config / Env loaders
# ============================================================


def load_yaml_config(path: Path | str = DEFAULT_THRESHOLDS) -> dict[str, Any]:
    """governance/thresholds.yaml load. PyYAML lazy import."""
    p = Path(path)
    if not p.exists():
        raise SystemExit(f"[ERROR] config not found: {p}")
    try:
        import yaml  # type: ignore
    except ImportError as exc:
        raise SystemExit(
            "[ERROR] PyYAML이 필요합니다. 'pip install -e .' 후 재시도."
        ) from exc
    with p.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_env_file(path: Path | str | None = None) -> dict[str, str]:
    """
    KEY=VALUE / 주석 / 빈 줄만 지원하는 minimal dotenv parser.

    `.env` 는 secret 만 (DART/KIS/FRED keys, Telegram tokens) 포함.
    비-secret runtime config 는 yaml 로 분리되어 있다:
        - $RUNTIME_POLICY_PATH + $RUNTIME_POLICY_LOCAL_PATH    (load_runtime_policy)
        - $USER_PORTFOLIO_PATH                                 (load_user_portfolio)
        - $USER_BEHAVIOR_PATH                                  (load_user_behavior)
        - $EXTERNAL_SIGNALS_MACRO_BREADTH_PATH                 (load_breadth_signal)

    경로 우선순위 (file):
        1. 인자 `path`
        2. `ENV_PATH` env var (alias resolver 가 export)
        3. `.env` (repo root)

    `.env` 가 .gitignore 이므로 worktree 에 존재하지 않는
    환경을 위해 os.environ 을 먼저 시도한다.
        Environment 탭에 등록된 secret/notify env 가 `os.environ` 에 주입되어
        있으므로, 본 함수가 알려진 key 들에 한해 fallback 으로 채택한다.
        File 값이 존재하는 key 는 file 우선 (local dev 의 명시적 override).
    """
    if path is None:
        path = os.environ.get("ENV_PATH") or DEFAULT_ENV
    p = Path(path)
    env: dict[str, str] = {}
    if p.exists():
        for raw in p.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            env[key.strip()] = value.split("#", 1)[0].strip()
    # file 미존재 또는 일부 key 누락 시 os.environ
    # 에서 알려진 secret/notify key 만 채택.  G21 정합 — 임의 env var 가
    # leak 되지 않도록 whitelist.
    _CLOUD_FALLBACK_KEYS = SECRET_ENV_KEYS | {
        "NOTIFY_CHANNELS",
        "NOTIFY_SLACK_CHANNEL",
        "NOTIFY_EMAIL_TO",
        "NOTIFY_EMAIL_FROM",
        "NOTIFY_DISCORD_WEBHOOK_URL",
        "NOTIFY_KAKAO_ACCESS_TOKEN",
        "NOTIFY_WEBHOOK_URL",
        "NOTIFY_WEBHOOK_AUTH",
    }
    for k in _CLOUD_FALLBACK_KEYS:
        if env.get(k, "").strip():
            continue  # file 값 우선
        v = os.environ.get(k, "").strip()
        if v:
            env[k] = v
    return env


# ============================================================
# Runtime policy / user context yaml loaders
# ============================================================


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """
    base ← override 깊은 merge (override 값 우선).
    list 는 replace, dict 는 recursive merge, scalar 는 override.
    """
    out = dict(base)
    for k, v in override.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _load_yaml_optional(path: Path) -> dict[str, Any]:
    """yaml load. 미존재 시 빈 dict (G8 graceful — caller 가 boundary 결정)."""
    if not path.exists():
        return {}
    try:
        import yaml  # type: ignore
    except ImportError as exc:
        raise SystemExit(
            "[ERROR] PyYAML 이 필요합니다. 'pip install -e .' 후 재시도."
        ) from exc
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        return {}
    return data


def load_runtime_policy() -> dict[str, Any]:
    """
    $RUNTIME_POLICY_PATH (base, 추적) + $RUNTIME_POLICY_LOCAL_PATH (사용자
    override, gitignore) deep-merge.  .local.yaml 미존재 시 base 만 반환.
    base 도 미존재 시 빈 dict (G8).

    schema (merged):
        agent.block_auto_trade: bool
        user_acknowledged.not_financial_advice: bool
        user_acknowledged.no_auto_trade: bool
        user_acknowledged.sample_size_limits: bool
        kis.read_only_account.enabled: bool

    .local.yaml gitignore 이므로 worktree 부재 환경에서
    env 가 set 이면 final merged 값을 추가 override 한다 — env 가
    가장 우선. False 표기 ("false"/"0"/"no") 도 명시적 override 로 인정.

    Env fallback mapping:
        RUNTIME_POLICY_USER_ACK_NOT_FINANCIAL_ADVICE  → user_acknowledged.not_financial_advice
        RUNTIME_POLICY_USER_ACK_NO_AUTO_TRADE         → user_acknowledged.no_auto_trade
        RUNTIME_POLICY_USER_ACK_SAMPLE_SIZE_LIMITS    → user_acknowledged.sample_size_limits
        RUNTIME_POLICY_KIS_READ_ONLY_ENABLED          → kis.read_only_account.enabled
    """
    base = _load_yaml_optional(REPO_ROOT / "governance" / "runtime-policy.yaml")
    local = _load_yaml_optional(REPO_ROOT / "governance" / "runtime-policy.local.yaml")
    merged = _deep_merge(base, local)

    def _env_bool(env_key: str) -> bool | None:
        v = os.environ.get(env_key, "").strip().lower()
        if v in ("true", "1", "yes", "y", "on"):
            return True
        if v in ("false", "0", "no", "n", "off"):
            return False
        return None

    _ENV_OVERRIDES = (
        (
            "RUNTIME_POLICY_USER_ACK_NOT_FINANCIAL_ADVICE",
            ("user_acknowledged", "not_financial_advice"),
        ),
        (
            "RUNTIME_POLICY_USER_ACK_NO_AUTO_TRADE",
            ("user_acknowledged", "no_auto_trade"),
        ),
        (
            "RUNTIME_POLICY_USER_ACK_SAMPLE_SIZE_LIMITS",
            ("user_acknowledged", "sample_size_limits"),
        ),
        (
            "RUNTIME_POLICY_KIS_READ_ONLY_ENABLED",
            ("kis", "read_only_account", "enabled"),
        ),
    )
    for env_key, path in _ENV_OVERRIDES:
        v = _env_bool(env_key)
        if v is None:
            continue
        cursor = merged
        for seg in path[:-1]:
            if seg not in cursor or not isinstance(cursor.get(seg), dict):
                cursor[seg] = {}
            cursor = cursor[seg]
        cursor[path[-1]] = v
    return merged


def all_user_acknowledged(
    policy: dict[str, Any] | None = None,
) -> tuple[bool, list[str]]:
    """
    runtime-policy 의 user_acknowledged 3 flag 모두 true 인지 검사.
    Returns (all_true, pending_keys).
    """
    if policy is None:
        policy = load_runtime_policy()
    ack = policy.get("user_acknowledged") or {}
    expected = ("not_financial_advice", "no_auto_trade", "sample_size_limits")
    pending = [k for k in expected if not bool(ack.get(k))]
    return (not pending), pending


def load_user_portfolio() -> dict[str, Any]:
    """
    $USER_PORTFOLIO_PATH load. 미존재 / 누락 필드 시 env fallback.

    schema:
        total_capital_krw:    int | None
        current_drawdown_pct: float | None
        current_cash_pct:     float | None
        volatility_tolerance: 'low' | 'medium' | 'high' | None  (helper 미참조)

    Env fallback (file gitignore 이므로 worktree 부재 시):
        USER_PORTFOLIO_TOTAL_KRW       → total_capital_krw    (int)
        USER_PORTFOLIO_DRAWDOWN_PCT    → current_drawdown_pct (float)
        USER_PORTFOLIO_CASH_PCT        → current_cash_pct     (float)
        File 값이 존재하면 file 우선, 빈 / None 인 경우만 env 채택.
    """
    data = _load_yaml_optional(REPO_ROOT / "config" / "user" / "portfolio.yaml")

    def _env_int(env_key: str) -> int | None:
        v = os.environ.get(env_key, "").strip()
        if not v:
            return None
        try:
            return int(v)
        except ValueError:
            return None

    def _env_float(env_key: str) -> float | None:
        v = os.environ.get(env_key, "").strip()
        if not v:
            return None
        try:
            return float(v)
        except ValueError:
            return None

    if not data.get("total_capital_krw"):
        fallback = _env_int("USER_PORTFOLIO_TOTAL_KRW")
        if fallback is not None:
            data["total_capital_krw"] = fallback
    if data.get("current_drawdown_pct") is None:
        fallback = _env_float("USER_PORTFOLIO_DRAWDOWN_PCT")
        if fallback is not None:
            data["current_drawdown_pct"] = fallback
    if data.get("current_cash_pct") is None:
        fallback = _env_float("USER_PORTFOLIO_CASH_PCT")
        if fallback is not None:
            data["current_cash_pct"] = fallback
    return data


def load_user_behavior() -> dict[str, Any]:
    """
    $USER_BEHAVIOR_PATH load. 미존재 시 빈 dict + env fallback.

    schema:
        yahoo_fallback.enabled: bool

    Env fallback (file gitignore 이므로 worktree 부재 시):
        USER_BEHAVIOR_YAHOO_FALLBACK_ENABLED  → yahoo_fallback.enabled
        File 값이 존재 (True/False 둘 다) 하면 file 우선.  env 는 file 키가
        없을 때만 채택.
    """
    data = _load_yaml_optional(REPO_ROOT / "config" / "user" / "behavior.yaml")

    def _env_bool(env_key: str) -> bool | None:
        v = os.environ.get(env_key, "").strip().lower()
        if v in ("true", "1", "yes", "y", "on"):
            return True
        if v in ("false", "0", "no", "n", "off"):
            return False
        return None

    yf = data.get("yahoo_fallback") or {}
    if "enabled" not in yf:
        v = _env_bool("USER_BEHAVIOR_YAHOO_FALLBACK_ENABLED")
        if v is not None:
            yf["enabled"] = v
            data["yahoo_fallback"] = yf
    return data


def user_config_dir() -> Path:
    """config/user — 사용자/배포 override 의 단일 위치 (ADR-0002 ownership axis / ADR-0015).

    gitignored (live 파일) + ``.example`` (tracked template) 관례. portfolio.yaml /
    behavior.yaml 와 동거. 사용자 결정(universe 수동 추가/제외 등)은 developer doctrine
    (governance/) 도 mechanical wiring (domains/*/config/) 도 아닌 본 위치.
    """
    return REPO_ROOT / "config" / "user"


def load_user_config_optional(filename: str) -> dict[str, Any]:
    """``config/user/{filename}`` graceful load (미존재 → {} ; gitignored worktree 부재 안전).

    ``filename`` 은 단순 basename (path 분리자 포함 시 ValueError — config root 탈출 방지).
    """
    if "/" in filename or ".." in filename:
        raise ValueError(f"load_user_config_optional: 단순 basename 만 허용 (got: {filename!r})")
    return _load_yaml_optional(user_config_dir() / filename)


def load_breadth_signal() -> dict[str, Any]:
    """
    config/signals/macro/breadth.yaml load. 미존재 시 빈 dict.

    예시 schema:
        spx_above_200dma_pct: float | None  (0.0 ~ 1.0)
        observed_at: str | None             (ISO date)
        source: str | None
    """
    return _load_yaml_optional(external_signals_dir() / "macro" / "breadth.yaml")


def resolve_allow_yahoo_fallback(cli_value: bool | None) -> bool:
    """
    Yahoo fallback 활성 여부 결정 — helper 들의 공통 패턴.

    우선순위:
        1. CLI `--allow-yahoo-fallback` 명시 (True) → True (사용자 명시 override)
        2. behavior.yaml.yahoo_fallback.enabled  (default False)

    Args:
        cli_value: argparse 결과. `--allow-yahoo-fallback` 가 명시되었으면 True,
                   None 이면 미명시 (yaml 결정).

    Returns:
        bool — Yahoo fallback 사용 여부.
    """
    if cli_value:
        return True
    behavior = load_user_behavior()
    return bool((behavior.get("yahoo_fallback") or {}).get("enabled", False))


# ============================================================
# Secret-safe logging
# ============================================================


_ACCOUNT_NUMBER_RE = re.compile(r"\b\d{8}-\d{2}\b")


def secret_safe_log(msg: str, env: dict[str, str]) -> str:
    """secret 환경변수 값이 메시지에 우연히 들어가는 경우 redact.

    1) env 의 SECRET_ENV_KEYS 값과 literal match — 가장 정확.
    2) `\\d{8}-\\d{2}` regex (KIS 계좌번호 형태) defense-in-depth — env 가
       다른 변형 (대시 위치, 동일 8-2 패턴 다른 secret 등) 으로 새는 경우 차단.
       false positive 가능성 있으나 audit log 노출보다 안전.
    """
    out = msg
    for key in SECRET_ENV_KEYS:
        val = env.get(key, "")
        if val and val in out:
            out = out.replace(val, f"<{key}_REDACTED>")
    out = _ACCOUNT_NUMBER_RE.sub("<ACCOUNT_NUMBER_REDACTED>", out)
    return out


def env_has_secret(env: dict[str, str], key: str) -> bool:
    """주어진 secret env 변수가 비어있지 않은지 확인."""
    return bool(env.get(key, "").strip())


# ============================================================
# Date / KST helpers
# ============================================================

_HOLIDAYS_CACHE: dict[str, set[str]] = {}
_HOLIDAYS_META_CACHE: dict[str, dict[str, Any]] = {}


def load_holidays(market: str = "KRX") -> set[str]:
    """
    휴장일 set load. 1차는 정적 JSON (`infrastructure/_common/_holidays_krx.json`).
    의존성 없음 — pandas-market-calendars / holidays 패키지 회피.

    `_meta.last_verified_date` 만료 (`stale_after_months` 초과) 시 stderr warning
    1회 (cache 됨, idempotent).

    Returns:
        set[str] of YYYY-MM-DD. 미존재 / 깨진 JSON 시 빈 set + warning.
    """
    if market in _HOLIDAYS_CACHE:
        return _HOLIDAYS_CACHE[market]
    if market.upper() != "KRX":
        _HOLIDAYS_CACHE[market] = set()
        return _HOLIDAYS_CACHE[market]
    p = Path(__file__).resolve().parent / "_holidays_krx.json"
    if not p.exists():
        sys.stderr.write(
            f"[holiday-calendar] WARN: {p.name} 미존재 — 공휴일 처리 비활성 (주말만 skip)\n"
        )
        _HOLIDAYS_CACHE[market] = set()
        return _HOLIDAYS_CACHE[market]
    try:
        with p.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        sys.stderr.write(f"[holiday-calendar] WARN: {p.name} JSON parse fail — {exc}\n")
        _HOLIDAYS_CACHE[market] = set()
        return _HOLIDAYS_CACHE[market]
    holidays = set(data.get("holidays") or [])
    meta = data.get("_meta") or {}
    _HOLIDAYS_META_CACHE[market] = meta

    # staleness check
    last_verified = meta.get("last_verified_date")
    stale_after = int(meta.get("stale_after_months", 6))
    if last_verified:
        try:
            lv = datetime.strptime(last_verified, "%Y-%m-%d").replace(tzinfo=KST)
            now = datetime.now(KST)
            months = (now - lv).total_seconds() / (30.4375 * 86400)
            if months > stale_after:
                sys.stderr.write(
                    f"[holiday-calendar] WARN: {p.name}.last_verified_date={last_verified} "
                    f"({months:.1f}개월 경과 > {stale_after}개월) — 사용자 manual 갱신 권장\n"
                )
        except ValueError:
            pass

    _HOLIDAYS_CACHE[market] = holidays
    return holidays


def is_trading_day(date_str: str, market: str = "KRX") -> bool:
    """주말 + 공휴일 양쪽 체크. KST 기준."""
    d = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=KST)
    if d.weekday() >= 5:
        return False
    return date_str not in load_holidays(market)


def normalize_to_trading_day(date_str: str | None, market: str = "KRX") -> str:
    """
    YYYY-MM-DD 입력을 KST 기준 가장 최근 거래일로 정규화.
    주말 + KRX 공휴일 모두 skip. holiday calendar 미로드 시 주말만 skip (graceful).
    """
    if date_str:
        d = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=KST)
    else:
        d = datetime.now(KST)
    holidays = load_holidays(market)
    while d.weekday() >= 5 or d.strftime("%Y-%m-%d") in holidays:
        d -= timedelta(days=1)
    return d.strftime("%Y-%m-%d")


def _previous_trading_day(date_str: str, market: str = "KRX") -> str:
    d = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=KST) - timedelta(days=1)
    holidays = load_holidays(market)
    while d.weekday() >= 5 or d.strftime("%Y-%m-%d") in holidays:
        d -= timedelta(days=1)
    return d.strftime("%Y-%m-%d")


def now_iso_kst() -> str:
    return datetime.now(KST).isoformat(timespec="seconds")


def now_iso_utc() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


# ============================================================
# Output (G20 — 덮어쓰기 금지)
# ============================================================


def write_output_safely(out_path: Path, payload: Any) -> Path:
    """
    이미 같은 경로에 파일이 존재하면 .{N}.suffix 형태로 보존.
    payload가 dataclass면 asdict, 아니면 dict / list 직접 직렬화.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    final_path = out_path
    if out_path.exists():
        n = 1
        while True:
            cand = out_path.with_name(out_path.stem + f".{n}" + out_path.suffix)
            if not cand.exists():
                final_path = cand
                break
            n += 1
    data = asdict(payload) if is_dataclass(payload) else payload
    with final_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return final_path


def write_yaml_safely(out_path: Path, payload: Any) -> Path:
    """write_output_safely 의 YAML 변종 — G20 collision 보존 + ``yaml.safe_dump``.

    governance/profiles/ 처럼 *사람이 리뷰하는* git-tracked SSoT 산출에 사용
    (JSON-in-.yaml 대신 가독성 있는 YAML). dataclass 는 asdict.
    """
    try:
        import yaml  # type: ignore
    except ImportError as exc:
        raise SystemExit(
            "[ERROR] PyYAML이 필요합니다. 'pip install -e .' 후 재시도."
        ) from exc
    out_path.parent.mkdir(parents=True, exist_ok=True)
    final_path = out_path
    if out_path.exists():
        n = 1
        while True:
            cand = out_path.with_name(out_path.stem + f".{n}" + out_path.suffix)
            if not cand.exists():
                final_path = cand
                break
            n += 1
    data = asdict(payload) if is_dataclass(payload) else payload
    with final_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False, indent=2)
    return final_path


# ============================================================
# Citation format (G7)
# ============================================================


def format_citation(source: str, ts: str, value: Any) -> str:
    """
    source citation 표준 포맷.
    예: format_citation('Yahoo', '2026-05-03T16:00', 178.50) → 'Yahoo@2026-05-03T16:00=178.5'
        format_citation('DART', '2026-05-03', {'rcept_no': '2026...'})
        → 'DART@2026-05-03={"rcept_no": "2026..."}'
    """
    if isinstance(value, (dict, list)):
        v = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    else:
        v = str(value)
    return f"{source}@{ts}={v}"


# ============================================================
# Minimal HTTP fetch (DART / FRED 공통)
# ============================================================


class FetchError(RuntimeError):
    """HTTP / parse / API status 실패 공통 exception. caller가 graceful degrade."""


# Retry-on HTTP status codes — transient server-side conditions.
# 429 (rate-limit), 500/502/503/504 (server errors). 401/403/404는 retry 안 함.
DEFAULT_RETRY_STATUS: tuple[int, ...] = (429, 500, 502, 503, 504)


def _is_transient_url_error(exc: Exception) -> bool:
    """urlopen timeout / DNS-flap / socket reset 같은 transient network 실패 판별.

    urlopen 의 reason 이 socket.timeout 인 경우 retry 후보로 본다.
    그 외 URLError (DNS 실패 등) 은 transient 가능하지만 보수적으로 retry 미적용.
    """
    if isinstance(exc, socket.timeout):
        return True
    if isinstance(exc, urllib.error.URLError):
        reason = getattr(exc, "reason", None)
        if isinstance(reason, socket.timeout):
            return True
        # `reason` 이 str 인 경우 ("timed out" 같은) — 일부 stdlib 버전
        if isinstance(reason, str) and "time" in reason.lower():
            return True
    return False


def _open_with_retry(
    req: urllib.request.Request,
    *,
    timeout: float,
    retry: int,
    retry_on: tuple[int, ...],
    backoff_base: float,
    url_for_error: str,
) -> str:
    """공통 urlopen wrapper — HTTPError(retry_on) / timeout 시 exponential backoff retry.

    retry=0 이면 기존 단발 호출 동작과 동일. 5xx/429/timeout 외에는 즉시 raise.
    """
    last_exc: Exception | None = None
    for attempt in range(retry + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            last_exc = exc
            if exc.code in retry_on and attempt < retry:
                time.sleep(backoff_base * (2**attempt) + random.uniform(0, 0.5))
                continue
            raise FetchError(f"HTTP fetch fail: {url_for_error} — {exc}") from exc
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if _is_transient_url_error(exc) and attempt < retry:
                time.sleep(backoff_base * (2**attempt) + random.uniform(0, 0.5))
                continue
            raise FetchError(f"HTTP fetch fail: {url_for_error} — {exc}") from exc
    # 도달 불가 — 위 loop 가 항상 return 또는 raise. 방어 코드.
    raise FetchError(f"HTTP fetch fail: {url_for_error} — {last_exc}")


def safe_http_json(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 10.0,
    user_agent: str = "investment-pipeline/1.0",
    retry: int = 0,
    retry_on: tuple[int, ...] = DEFAULT_RETRY_STATUS,
    backoff_base: float = 1.0,
) -> dict[str, Any]:
    """GET → JSON parse. 실패 시 FetchError raise (G8 — caller가 hallucination 대신 warning 처리).

    retry>0 시 5xx/429/timeout 에 한해 exponential backoff (backoff_base * 2^attempt + jitter).
    """
    full_url = url
    if params:
        full_url = f"{url}?{urllib.parse.urlencode(params)}"
    hdr = {"User-Agent": user_agent}
    if headers:
        hdr.update(headers)
    req = urllib.request.Request(full_url, headers=hdr)
    raw = _open_with_retry(
        req,
        timeout=timeout,
        retry=retry,
        retry_on=retry_on,
        backoff_base=backoff_base,
        url_for_error=url,
    )
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise FetchError(
            f"JSON parse fail: {url} — first 200 chars: {raw[:200]!r}"
        ) from exc


def safe_http_text(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 10.0,
    user_agent: str = "investment-pipeline/1.0",
    retry: int = 0,
    retry_on: tuple[int, ...] = DEFAULT_RETRY_STATUS,
    backoff_base: float = 1.0,
) -> str:
    """GET → text. 실패 시 FetchError raise. retry semantics는 safe_http_json 와 동일."""
    full_url = url
    if params:
        full_url = f"{url}?{urllib.parse.urlencode(params)}"
    hdr = {"User-Agent": user_agent}
    if headers:
        hdr.update(headers)
    req = urllib.request.Request(full_url, headers=hdr)
    return _open_with_retry(
        req,
        timeout=timeout,
        retry=retry,
        retry_on=retry_on,
        backoff_base=backoff_base,
        url_for_error=url,
    )


# ============================================================
# Stage report base helpers
# ============================================================


def base_report_envelope(
    *,
    schema: str,
    date: str,
    config_path: Path | str,
    config_version: int | str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    각 stage report의 표준 envelope.
    개별 stage는 'entries' / 'stats' / 'warnings' 등을 자체 schema로 추가.
    """
    env: dict[str, Any] = {
        "schema": schema,
        "generated_at": now_iso_kst(),
        "date": date,
        "config_path": str(config_path),
        "config_version": config_version,
    }
    if extra:
        env.update(extra)
    return env


# ============================================================
# Iter helper (rate limit pause for paged API)
# ============================================================


def paged_with_pause(
    items: Iterable[Any], *, pause_seconds: float = 0.05
) -> Iterable[Any]:
    """generator 사이 짧은 pause 삽입 (DART 등 rate-limit courtesy)."""
    for it in items:
        yield it
        if pause_seconds > 0:
            time.sleep(pause_seconds)


# ============================================================
# CLI helpers
# ============================================================


def emit_summary_line(stage_name: str, summary: dict[str, Any], out_path: Path) -> None:
    """stdout 1줄 요약. handoff doc Section 5 의 표준 보고 형태."""
    parts = " ".join(f"{k}={v}" for k, v in summary.items())
    print(f"[{stage_name}] {parts} -> {out_path}", file=sys.stdout)
