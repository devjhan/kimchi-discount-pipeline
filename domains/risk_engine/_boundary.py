"""risk_engine bounded context 의 외부 의존 단일 게이트 (anti-corruption layer).

다른 risk_engine 모듈은 외부 시스템(infrastructure._common.utils / infrastructure.kis /
positions 스토어 / file system 경로)에 직접 접근하지 않고 본 모듈을 통과한다.
screener/universe ``_boundary.py`` 와 동형 — 단, risk_engine 은 (1) KIS 계좌를 read 하고
(2) positions thesis 스토어를 소유하므로 그 둘을 추가로 게이트한다.

**G9 단일 게이트.** KIS 접근은 본 모듈의 6개 read-only 게이트웨이로만 가능하다 —
order/trade endpoint 는 *surface 자체를 안 함* → 호출 불가가 곧 구조적 G9 강제.
``KisAutoTradeBlocked`` 는 caller 가 즉시 raise 하도록 re-export (G9c).

레이어: 본 모듈만 ``infrastructure`` 를 import 한다(게이트). 다른 risk_engine 파일은
``from domains.risk_engine._boundary import ...`` 로 우회 — 그래서
``grep "from infrastructure" domains/risk_engine/ | grep -v _boundary.py`` → 0.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from infrastructure._common import utils as _utils
from infrastructure.kis import client as _kis

from domains._shared.positions_store.store import PositionsStore
from domains.risk_engine.ports.kis_account import KisAccountPort

# ----------------------------------------------------------------------
# Constants re-export (raw infrastructure import 우회용)
# ----------------------------------------------------------------------

KST = _utils.KST
DEFAULT_THRESHOLDS = _utils.DEFAULT_THRESHOLDS
DEFAULT_ENV = _utils.DEFAULT_ENV
FetchError = _utils.FetchError

# KIS 예외 re-export — caller 의 except 절에서 사용.
KisAutoTradeBlocked = _kis.KisAutoTradeBlocked
KisUnavailable = _kis.KisUnavailable


# ----------------------------------------------------------------------
# Path / time / citation
# ----------------------------------------------------------------------


def resolve_positions_dir() -> Path:
    """``telemetry/positions`` 절대경로 ($POSITIONS_DIR env 우선). 본 함수가 단일 지점."""
    return _utils.positions_dir()


def resolve_account_dir() -> Path:
    """``telemetry/positions/_account`` 절대경로 — account-level 산출물(summary→derived) 루트.

    per-ticker ``{ticker}/`` 디렉토리와 분리된 계좌 단위 산출물 그룹 ($POSITIONS_ACCOUNT_DIR
    env 우선, 미설정 시 positions_dir()/_account).
    """
    return _utils.positions_account_dir()


def resolve_trail_dir(date: str | None = None) -> Path:
    """오늘(또는 지정 일자)의 trail 디렉토리 절대경로 ($TRAIL_TODAY env 우선)."""
    return _utils.trail_dir(date)


def now_iso_kst() -> str:
    """현재 KST 시각의 ISO8601 표현 (citation timestamp 용)."""
    return _utils.now_iso_kst()


def now_kst() -> datetime:
    """현재 KST datetime (tz-aware)."""
    return datetime.now(_utils.KST)


def format_citation(source: str, ts: str, value: Any) -> str:
    """G7 형식 citation 문자열: ``{SOURCE}@{ISO_KST}={VALUE}``."""
    return _utils.format_citation(source, ts, value)


# ----------------------------------------------------------------------
# Output emit (re-export — call site 보존)
# ----------------------------------------------------------------------

base_report_envelope = _utils.base_report_envelope
emit_summary_line = _utils.emit_summary_line
write_output_safely = _utils.write_output_safely


# ----------------------------------------------------------------------
# Config / env (re-export)
# ----------------------------------------------------------------------

load_env_file = _utils.load_env_file
load_yaml_config = _utils.load_yaml_config
load_user_portfolio = _utils.load_user_portfolio
normalize_to_trading_day = _utils.normalize_to_trading_day
secret_safe_log = _utils.secret_safe_log


# ----------------------------------------------------------------------
# positions thesis 스토어 (F-5b seam)
# ----------------------------------------------------------------------


def positions_store(root: Path | None = None) -> PositionsStore:
    """PositionsStore — root 미지정 시 resolve_positions_dir(). 3 monitor 의 단일 로더 출처."""
    return PositionsStore(root=root if root is not None else resolve_positions_dir())


def commit_thesis(thesis: Any) -> Path:
    """thesis.json write. writer(``write_output_safely``)를 store 에 주입(G20)."""
    return positions_store().commit(thesis, writer=_utils.write_output_safely)


def load_derived_state(
    date: str, *, positions_dir: Path | None = None
) -> dict[str, Any] | None:
    """``_account/derived-{date}.json`` payload read (sizing fallback).

    sizing → portfolio_state_derive 모듈 순환 의존을 끊기 위해 read 를 본 게이트에 둠.
    파일 미존재 / parse 실패 → None (caller graceful).
    """
    root = positions_dir if positions_dir is not None else resolve_positions_dir()
    p = root / "_account" / f"derived-{date}.json"
    if not p.exists():
        return None
    try:
        with p.open("r", encoding="utf-8") as f:
            envelope = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None
    return (envelope or {}).get("payload") or envelope


# ----------------------------------------------------------------------
# KIS read-only 게이트웨이 (G9 — 6 endpoint 만, order/trade 미노출)
# ----------------------------------------------------------------------


def kis_read_only_enabled() -> tuple[bool, str | None]:
    """runtime-policy 검사. (활성, skip_reason). G9b — read-only whitelist 게이트."""
    policy = _utils.load_runtime_policy()
    section = (policy.get("kis") or {}).get("read_only_account") or {}
    if not section.get("enabled"):
        return (
            False,
            "kis.read_only_account.enabled=false (runtime-policy.local.yaml override 필요)",
        )
    return True, None


def _kis_token_cache_path() -> Path:
    """secrets/.kis_token.json (자격증명, chmod 0600)."""
    return _utils.repo_path("secrets", ".kis_token.json")


def kis_issue_access_token(env: dict[str, str]) -> str:
    """KIS OAuth 토큰 발급 (캐시 경로 내부 주입). 실패 시 KisUnavailable."""
    return _kis.issue_access_token(env, cache_path=_kis_token_cache_path())


def kis_fetch_account_balance(**kwargs: Any) -> dict[str, Any]:
    return _kis.fetch_account_balance(**kwargs)


def kis_fetch_buyable_amount(**kwargs: Any) -> dict[str, Any]:
    return _kis.fetch_buyable_amount(**kwargs)


def kis_fetch_account_assets(**kwargs: Any) -> dict[str, Any]:
    return _kis.fetch_account_assets(**kwargs)


def kis_fetch_realized_pnl(**kwargs: Any) -> dict[str, Any]:
    return _kis.fetch_realized_pnl(**kwargs)


def kis_fetch_sellable_qty(*, stock_code: str, **kwargs: Any) -> dict[str, Any]:
    return _kis.fetch_sellable_qty(stock_code=stock_code, **kwargs)


# ----------------------------------------------------------------------
# KisAccountPort adapter (G9c — type-level read-only, order surface 부재)
# ----------------------------------------------------------------------


class _KisAccountAdapter:
    """KisAccountPort impl — _kis read endpoint 위임. order 메서드 미존재 = G9c."""

    def issue_access_token(self, env: dict[str, str]) -> str:
        """KIS OAuth 토큰 발급 (캐시 경로 내부 주입)."""
        return _kis.issue_access_token(env, cache_path=_kis_token_cache_path())

    def fetch_account_balance(self, **kwargs: Any) -> dict[str, Any]:
        """보유 잔고."""
        return _kis.fetch_account_balance(**kwargs)

    def fetch_buyable_amount(self, **kwargs: Any) -> dict[str, Any]:
        """매수가능 현금성."""
        return _kis.fetch_buyable_amount(**kwargs)

    def fetch_account_assets(self, **kwargs: Any) -> dict[str, Any]:
        """계좌 자산 종합."""
        return _kis.fetch_account_assets(**kwargs)

    def fetch_realized_pnl(self, **kwargs: Any) -> dict[str, Any]:
        """실현손익."""
        return _kis.fetch_realized_pnl(**kwargs)

    def fetch_sellable_qty(self, *, stock_code: str, **kwargs: Any) -> dict[str, Any]:
        """종목별 매도가능수량."""
        return _kis.fetch_sellable_qty(stock_code=stock_code, **kwargs)


def kis_account_adapter() -> KisAccountPort:
    """KisAccountPort 어댑터 factory — composition root(positions_sync.main) 주입용.

    sync_account 은 본 factory 가 반환한 read-only port 에만 의존 → order 메서드 호출이
    타입상 불가능 (G9c 4번째 구조 가드). 기존 free fn(``kis_fetch_*``)은 back-compat 잔류.
    """
    return _KisAccountAdapter()
