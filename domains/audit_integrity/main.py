"""audit_integrity CLI — 4-tier shadow portfolio 일별 결정론 update (구 LLM 스킬 회수, F-6).

usage:
    python -m domains.audit_integrity.main --date 2026-05-17
    python -m domains.audit_integrity.main --allow-yahoo-fallback

state (``$AUDIT_DIR/shadow-portfolio-state.json``) 부재 시 Mode B — init 안내 후 exit 2.
모든 가격 source 미가용 시 Mode C — snapshot 미저장 + warning. paper trade only (G9).

산출: shadow-portfolio-state.json (atomic in-place update) + trade-log-{tier}.csv (append).
분기 비교 / self-disable 는 investment-audit-outcome 스킬 (stat_tests 소비) 책임 — 본 엔진은
결정론 state 만 갱신.
"""
from __future__ import annotations

import argparse
import sys

from domains.audit_integrity import _boundary
from domains.audit_integrity.application.run_daily_update import (
    DailyInputs,
    EngineConfig,
    run_daily_update,
)
from domains.audit_integrity.domain.rules import select_top_k_catalyst_tickers
from domains.audit_integrity.io import state_store, trade_log
from domains.audit_integrity.io.price_source import PriceSource
from domains.audit_integrity.io.trail_loader import (
    load_catalysts,
    load_falsifier_triggered,
    load_sizing_recs,
    load_universe_quality_pool,
    primary_catalyst_tickers,
)

STAGE_NAME = "audit-shadow-portfolio"
_DEFAULT_TIER0 = ["US:SPY", "KR:069500"]


def _engine_config(sp: dict) -> EngineConfig:
    return EngineConfig(
        top_k=int(sp.get("top_k", 5)),
        max_hold_days=int(sp.get("max_hold_days", 30)),
        rebalance_threshold_pct=float(sp.get("rebalance_threshold_pct", 0.05)),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="domains.audit_integrity.main",
        description="4-tier shadow portfolio 일별 paper-trade update (결정론).",
    )
    parser.add_argument("--date", help="YYYY-MM-DD (KST). 기본: 오늘 거래일.")
    parser.add_argument(
        "--allow-yahoo-fallback",
        action="store_true",
        default=None,
        help="KIS 미가용 시 Yahoo 사용 (미명시 시 config/user/behavior.yaml 결정).",
    )
    args = parser.parse_args(argv)

    date = _boundary.normalize_to_trading_day(args.date)

    state = state_store.load_state()
    if state is None:
        print(
            "[ERROR] shadow-portfolio-state.json 부재 (Mode B). 먼저 init:\n"
            "        python -m domains.audit_integrity.init_shadow_state",
            file=sys.stderr,
        )
        return 2

    thresholds = _boundary.load_thresholds()
    sp_cfg = (thresholds.get("statistics") or {}).get("shadow_portfolio") or {}
    config = _engine_config(sp_cfg)
    tier0_tickers = tuple(sp_cfg.get("tier0_tickers") or _DEFAULT_TIER0)

    env = _boundary.load_env()
    allow_yahoo = _boundary.resolve_allow_yahoo_fallback(args.allow_yahoo_fallback)

    # ----- inputs -----
    warnings: list[str] = []
    catalysts, w = load_catalysts(date)
    warnings += w
    recs, w = load_sizing_recs(date)
    warnings += w
    pool, w = load_universe_quality_pool(date)
    warnings += w

    inputs = DailyInputs(
        date=date,
        tier0_tickers=tier0_tickers,
        tier1_candidates=tuple(select_top_k_catalyst_tickers(catalysts, config.top_k)),
        tier1_active_catalysts=primary_catalyst_tickers(catalysts),
        tier2_recs=tuple(recs),
        tier2_falsifier_triggered=load_falsifier_triggered(date),
        tier3_pool=tuple(pool),
    )

    price_source = PriceSource(env, date=date, allow_yahoo=allow_yahoo)

    result = run_daily_update(state, inputs, config, price_source.price_for)
    for wmsg in result.warnings:
        warnings.append(_boundary.secret_safe_log(wmsg, env))

    # ----- Mode C: 모든 가격 source 미가용 → snapshot 미저장 -----
    if not result.citations:
        print(
            f"[{STAGE_NAME}] Mode C — 모든 가격 source 미가용. snapshot 미저장 (state 보존).",
            file=sys.stderr,
        )
        out = state_store.state_path()
        _boundary.emit_summary(
            STAGE_NAME,
            {"date": date, "mode": "all_price_unavailable", "warnings": len(warnings)},
            out,
        )
        return 0

    saved = state_store.save_state(result.state)
    trade_log.append_closed_trades(result.closed_trades)

    _boundary.emit_summary(
        STAGE_NAME,
        {
            "date": date,
            "tiers": len(result.state.tiers),
            "closed_trades": len(result.closed_trades),
            "prices_cited": len(result.citations),
            "warnings": len(warnings),
        },
        saved,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
