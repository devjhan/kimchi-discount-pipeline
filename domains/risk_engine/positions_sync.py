#!/usr/bin/env python3
"""
domains/risk_engine/positions_sync.py — KIS 계좌 read-only sync.

`infrastructure.kis.client` 의 6 종 read-only endpoint 를 호출해 사용자 계좌의
보유 종목 / 평가 / 매수가능 / 매도가능 / 실현 PnL / 일별 체결 / 총자산을 조회하고
다음 산출물을 생성:

    $POSITIONS_DIR/_account/summary-{date}.json
    $POSITIONS_DIR/{KR_xxxxxx}/balance-{date}.json    (보유 종목별)

본 helper 는 G9b/G9c 정책 (`kis.read_only_account.enabled` whitelist) 위에서만
동작 — runtime-policy.local.yaml 의 enabled=false (default) 환경에서는 graceful
skip + warning. KIS_ACCOUNT_NUMBER 미설정 / KIS 키 미설정 시도 동일 graceful skip.

본 helper 는 어떤 매매/주문 endpoint 도 호출하지 않는다 (G9a). KIS client 의
`KisAutoTradeBlocked` 가 발생하면 즉시 비-graceful raise (audit 신호).

Hard guards:
    - G6: positions 통계 합계는 deterministic 산식 (LLM 위임 금지)
    - G7: 모든 잔고/현금 숫자에 source citation (KIS@<ts>=<value>)
    - G8: KIS HTTP 실패 시 graceful skip + skip_reason
    - G9b: read-only endpoint 만 호출 (kis client 가 정책 검사)
    - G9c: KisAutoTradeBlocked 발생 시 즉시 raise
    - G20: balance-{date}.json 덮어쓰기 금지 — .{N}.json suffix 자동
    - G21: 계좌번호는 secret_safe_log 로 redact (산출물 본문에는 mask 형태만)

Run:
    python -m domains.risk_engine.positions_sync [--date YYYY-MM-DD] [--dry-run]
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from domains.risk_engine._boundary import (
    KisAutoTradeBlocked,
    KisUnavailable,
    base_report_envelope,
    emit_summary_line,
    format_citation,
    kis_account_adapter,
    kis_read_only_enabled,
    load_env_file,
    normalize_to_trading_day,
    now_iso_kst,
    resolve_account_dir as _account_dir,
    resolve_positions_dir as _positions_dir,
    secret_safe_log,
    write_output_safely,
)
from domains.risk_engine.ports.kis_account import KisAccountPort

SCHEMA_VERSION = "investment-positions-sync-v1"
STAGE_NAME = "positions-sync"


@dataclass
class PerTickerSnapshot:
    ticker: str
    name: str
    quantity: int
    avg_price: float | None
    current_price: float | None
    eval_amount: float | None
    purchase_amount: float | None
    eval_pnl: float | None
    eval_pnl_pct: float | None
    sellable_qty: int | None
    realized_pnl_period: float | None
    citations: list[str] = field(default_factory=list)


@dataclass
class AccountSummary:
    schema: str = SCHEMA_VERSION
    date: str = ""
    sync_status: str = "ok"  # 'ok' | 'skipped' | 'partial'
    skip_reason: str | None = None
    total_assets_krw: float | None = None
    cash_krw: float | None = None
    holdings_count: int = 0
    buyable_cash_krw: float | None = None
    eval_pnl_total: float | None = None
    realized_pnl_period: float | None = None
    citations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    holdings: list[dict[str, Any]] = field(default_factory=list)


def _to_float(v: Any) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _to_int(v: Any) -> int:
    f = _to_float(v)
    return int(f) if f is not None else 0


def _gate_enabled() -> tuple[bool, str | None]:
    """runtime-policy 검사. (활성, skip_reason). G9 게이트는 _boundary 단일 소유."""
    return kis_read_only_enabled()


def _build_per_ticker(
    raw_holding: dict[str, Any],
    *,
    sellable_qty: int | None,
    realized_pnl: float | None,
    ts: str,
) -> PerTickerSnapshot:
    """KIS output1 row 1건 → PerTickerSnapshot. 모든 숫자에 G7 citation."""
    code = str(raw_holding.get("pdno") or "").strip()
    # 도메인 canonical 티커 형식 KR:NNNNNN (catalyst/screener/thesis 와 일치).
    # 디렉토리는 write_artifacts 에서 KR_NNNNNN 으로 sanitize (registry ^KR_\d+$).
    ticker = f"KR:{code}" if code else ""
    name = str(raw_holding.get("prdt_name") or "").strip()
    qty = _to_int(raw_holding.get("hldg_qty"))
    avg_price = _to_float(raw_holding.get("pchs_avg_pric"))
    current_price = _to_float(raw_holding.get("prpr"))
    eval_amount = _to_float(raw_holding.get("evlu_amt"))
    purchase_amount = _to_float(raw_holding.get("pchs_amt"))
    eval_pnl = _to_float(raw_holding.get("evlu_pfls_amt"))
    eval_pnl_pct = _to_float(raw_holding.get("evlu_pfls_rt"))
    citations: list[str] = []
    for label, value in (
        ("eval_amount", eval_amount),
        ("eval_pnl", eval_pnl),
        ("avg_price", avg_price),
        ("current_price", current_price),
    ):
        if value is not None:
            citations.append(format_citation(f"KIS@{ts}#{label}", ts, value))
    return PerTickerSnapshot(
        ticker=ticker,
        name=name,
        quantity=qty,
        avg_price=avg_price,
        current_price=current_price,
        eval_amount=eval_amount,
        purchase_amount=purchase_amount,
        eval_pnl=eval_pnl,
        eval_pnl_pct=eval_pnl_pct,
        sellable_qty=sellable_qty,
        realized_pnl_period=realized_pnl,
        citations=citations,
    )


def sync_account(
    *, date: str, env: dict[str, str], account: KisAccountPort
) -> AccountSummary:
    """KIS 6 endpoint 호출 → AccountSummary. KIS_AUTO_TRADE_BLOCKED 외 모두 graceful.

    ``account`` (KisAccountPort) 은 composition root(main)가 주입한 read-only 어댑터 —
    order 메서드가 surface 에 없어 매매 호출이 타입상 불가능 (G9c).
    """
    summary = AccountSummary(date=date)

    enabled, gate_reason = _gate_enabled()
    if not enabled:
        summary.sync_status = "skipped"
        summary.skip_reason = gate_reason
        return summary

    app_key = (env.get("KIS_APP_KEY") or "").strip()
    app_secret = (env.get("KIS_APP_SECRET") or "").strip()
    account_number = (env.get("KIS_ACCOUNT_NUMBER") or "").strip()
    if not (app_key and app_secret and account_number):
        summary.sync_status = "skipped"
        missing = [
            k
            for k, v in (
                ("KIS_APP_KEY", app_key),
                ("KIS_APP_SECRET", app_secret),
                ("KIS_ACCOUNT_NUMBER", account_number),
            )
            if not v
        ]
        summary.skip_reason = f"env missing: {','.join(missing)}"
        return summary

    # token cache(secrets/.kis_token.json) 경로는 _boundary 가 내부 주입 (G9/G21)
    try:
        token = account.issue_access_token(env)
    except KisUnavailable as exc:
        summary.sync_status = "skipped"
        summary.skip_reason = secret_safe_log(f"token issue fail: {exc}", env)
        return summary

    ts = now_iso_kst()
    common_kwargs = dict(
        token=token,
        app_key=app_key,
        app_secret=app_secret,
        account_number=account_number,
    )

    # 1) 보유 잔고
    holdings_raw: list[dict[str, Any]] = []
    try:
        bal = account.fetch_account_balance(**common_kwargs)
        holdings_raw = bal.get("positions") or []
        bal_summary = (bal.get("summary") or [{}])[0] if bal.get("summary") else {}
        summary.total_assets_krw = _to_float(bal_summary.get("tot_evlu_amt"))
        summary.cash_krw = _to_float(bal_summary.get("dnca_tot_amt"))
        summary.eval_pnl_total = _to_float(bal_summary.get("evlu_pfls_smtl_amt"))
        for label in ("total_assets_krw", "cash_krw", "eval_pnl_total"):
            v = getattr(summary, label)
            if v is not None:
                summary.citations.append(format_citation(f"KIS@{ts}#{label}", ts, v))
    except KisAutoTradeBlocked:
        raise  # G9c — 즉시 raise, graceful 금지
    except KisUnavailable as exc:
        summary.warnings.append(secret_safe_log(f"account_balance fail: {exc}", env))
        summary.sync_status = "partial"

    # 2) 매수가능 (현금성)
    try:
        psbl = account.fetch_buyable_amount(**common_kwargs)
        summary.buyable_cash_krw = _to_float(psbl.get("ord_psbl_cash"))
        if summary.buyable_cash_krw is not None:
            summary.citations.append(
                format_citation(f"KIS@{ts}#buyable_cash_krw", ts, summary.buyable_cash_krw)
            )
    except KisAutoTradeBlocked:
        raise
    except KisUnavailable as exc:
        summary.warnings.append(secret_safe_log(f"buyable_amount fail: {exc}", env))
        summary.sync_status = "partial"

    # 3) 계좌 자산 종합 (CTRP6548R) — total_assets fallback
    try:
        assets = account.fetch_account_assets(**common_kwargs)
        totals = assets.get("totals") or {}
        if summary.total_assets_krw is None:
            summary.total_assets_krw = _to_float(totals.get("tot_asst_amt"))
            if summary.total_assets_krw is not None:
                summary.citations.append(
                    format_citation(
                        f"KIS@{ts}#total_assets_krw_fallback", ts, summary.total_assets_krw
                    )
                )
    except KisAutoTradeBlocked:
        raise
    except KisUnavailable as exc:
        summary.warnings.append(secret_safe_log(f"account_assets fail: {exc}", env))
        if summary.sync_status == "ok":
            summary.sync_status = "partial"

    # 4) 실현손익 (전체 종목 합산)
    realized_per_ticker: dict[str, float | None] = {}
    try:
        rpnl = account.fetch_realized_pnl(**common_kwargs)
        for row in rpnl.get("positions") or []:
            tk = str(row.get("pdno") or "").strip()
            realized_per_ticker[tk] = _to_float(row.get("rlzt_pfls"))
        rpnl_sum = (rpnl.get("summary") or [{}])[0] if rpnl.get("summary") else {}
        summary.realized_pnl_period = _to_float(rpnl_sum.get("rlzt_pfls_smtl"))
        if summary.realized_pnl_period is not None:
            summary.citations.append(
                format_citation(
                    f"KIS@{ts}#realized_pnl_period", ts, summary.realized_pnl_period
                )
            )
    except KisAutoTradeBlocked:
        raise
    except KisUnavailable as exc:
        summary.warnings.append(secret_safe_log(f"realized_pnl fail: {exc}", env))
        if summary.sync_status == "ok":
            summary.sync_status = "partial"

    # 5) 보유 종목별 매도가능수량 + per-ticker snapshot 생성
    per_ticker_snapshots: list[PerTickerSnapshot] = []
    for raw in holdings_raw:
        tk = str(raw.get("pdno") or "").strip()
        if not tk or len(tk) != 6 or not tk.isdigit():
            continue
        sellable: int | None = None
        try:
            s = account.fetch_sellable_qty(stock_code=tk, **common_kwargs)
            sellable = _to_int(s.get("nrcvb_buy_qty") or s.get("ord_psbl_qty"))
        except KisAutoTradeBlocked:
            raise
        except KisUnavailable as exc:
            summary.warnings.append(
                secret_safe_log(f"sellable_qty[{tk}] fail: {exc}", env)
            )
        snap = _build_per_ticker(
            raw,
            sellable_qty=sellable,
            realized_pnl=realized_per_ticker.get(tk),
            ts=ts,
        )
        per_ticker_snapshots.append(snap)

    summary.holdings_count = len(per_ticker_snapshots)
    summary.holdings = [asdict(s) for s in per_ticker_snapshots]
    return summary


def write_artifacts(summary: AccountSummary, env: dict[str, str]) -> list[Path]:
    """summary + per-ticker snapshot 파일 작성. G20 .{N}.json suffix.

    account-level summary 는 ``_account/summary-{date}.json`` (derived 계보와 동거),
    per-ticker balance 는 ``{KR_xxxxxx}/balance-{date}.json`` (콜론 sanitize).
    """
    positions_dir = _positions_dir()
    account_dir = _account_dir()
    written: list[Path] = []

    # 1) summary (account-level)
    summary_path = account_dir / f"summary-{summary.date}.json"
    envelope = base_report_envelope(
        schema=SCHEMA_VERSION,
        date=summary.date,
        config_path=str(summary_path),
        config_version=1,
    )
    envelope["payload"] = asdict(summary)
    written.append(write_output_safely(summary_path, envelope))

    # 2) per-ticker
    for snap in summary.holdings:
        ticker = snap.get("ticker") or ""
        if not ticker:
            continue
        # 콜론 sanitize: 'KR:005930' → 'KR_005930' (registry id_validator ^KR_\d+$).
        scope_dir = ticker.replace(":", "_").replace("/", "_")
        per_path = positions_dir / scope_dir / f"balance-{summary.date}.json"
        per_envelope = base_report_envelope(
            schema=SCHEMA_VERSION + "-perticker",
            date=summary.date,
            config_path=str(per_path),
            config_version=1,
        )
        per_envelope["payload"] = snap
        written.append(write_output_safely(per_path, per_envelope))
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description="KIS read-only positions sync")
    parser.add_argument("--date", default=None, help="YYYY-MM-DD (default: today KST)")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="API 호출 없이 정책 게이트 + env check 만 실행",
    )
    parser.add_argument(
        "--trail-dir",
        default=None,
        help="(unused — positions_sync 는 _positions/ 에 직접 write)",
    )
    args = parser.parse_args()

    date = normalize_to_trading_day(args.date)
    env = load_env_file()

    if args.dry_run:
        enabled, reason = _gate_enabled()
        result = {
            "stage": STAGE_NAME,
            "date": date,
            "dry_run": True,
            "policy_enabled": enabled,
            "skip_reason": reason,
            "env_keys_set": [
                k
                for k in ("KIS_APP_KEY", "KIS_APP_SECRET", "KIS_ACCOUNT_NUMBER")
                if env.get(k, "").strip()
            ],
        }
        emit_summary_line(STAGE_NAME, result, Path("/dev/null"))
        return 0

    try:
        # composition root: read-only KisAccountPort 어댑터 구성 → 주입 (G9c)
        summary = sync_account(date=date, env=env, account=kis_account_adapter())
    except KisAutoTradeBlocked as exc:
        # G9c — fail loudly, NOT graceful
        print(
            f"[FATAL] {STAGE_NAME}: KIS auto-trade blocked endpoint invoked: "
            f"{secret_safe_log(str(exc), env)}",
            file=sys.stderr,
        )
        return 2

    written = write_artifacts(summary, env)
    summary_dict = {
        "stage": STAGE_NAME,
        "date": date,
        "sync_status": summary.sync_status,
        "skip_reason": summary.skip_reason,
        "holdings_count": summary.holdings_count,
        "warnings_count": len(summary.warnings),
        "files_written": [str(p) for p in written],
    }
    primary = written[0] if written else Path("/dev/null")
    emit_summary_line(STAGE_NAME, summary_dict, primary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
