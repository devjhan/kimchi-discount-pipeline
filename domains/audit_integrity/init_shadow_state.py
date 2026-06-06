#!/usr/bin/env python3
"""
init_shadow_state.py — 4-tier shadow portfolio state 초기화.

`domains.audit_integrity.main` 결정론 엔진(F-6)이 일별 갱신할 state 파일의
초기 template을 생성한다. 한 번만 실행 (이미 존재하면 거부 — 사용자 명시
재초기화는 --force 필요).

Hard guards:
    - G6: NAV / 수익률 모든 정량은 본 helper에서만 계산
    - G9: 실제 broker 호출 없음 — paper trade only
    - G20: 기존 state 존재 시 자동 덮어쓰기 금지 (--force flag 필수)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from infrastructure._common.utils import (
    audit_dir as _audit_dir,
    DEFAULT_THRESHOLDS,
    base_report_envelope,
    emit_summary_line,
    load_yaml_config,
    normalize_to_trading_day,
    write_output_safely,
)

SCHEMA_VERSION = "investment-shadow-portfolio-state-v1"
STAGE_NAME = "audit-init-shadow-state"


def _empty_tier(name: str, initial_capital_krw: float) -> dict:
    return {
        "name": name,
        "initial_capital_krw": initial_capital_krw,
        "current_nav_krw": initial_capital_krw,
        "cumulative_return_pct": 0.0,
        "current_holdings": [],
        "open_trades": 0,
        "closed_trades": 0,
        "last_rebalance_date": None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize 4-tier shadow portfolio state")
    parser.add_argument("--date", help="YYYY-MM-DD (KST). 기본: 오늘 (주말이면 직전 거래일)")
    parser.add_argument("--config", default=str(DEFAULT_THRESHOLDS))
    parser.add_argument("--trail-dir", default=None, help="output trail dir (default: $TRAIL_TODAY env, else operations/{KST 거래일})")
    parser.add_argument(
        "--force",
        action="store_true",
        help="기존 state 파일 존재 시 새 .{N}.json suffix로 별도 보존 (덮어쓰지 않음)",
    )
    args = parser.parse_args()

    config = load_yaml_config(args.config)
    date = normalize_to_trading_day(args.date)
    out_path = _audit_dir() / "shadow-portfolio-state.json"
    if out_path.exists() and not args.force:
        print(
            f"[ERROR] shadow-portfolio-state.json already exists: {out_path}\n"
            "        --force 사용 시 새 .{N}.json suffix로 별도 보존됨 (기존 file 보존, 덮어쓰지 않음).",
            file=sys.stderr,
        )
        return 2

    stats_cfg = config.get("statistics", {})
    initial_capital = float(
        stats_cfg.get("shadow_portfolio", {}).get("initial_capital_krw", 100_000_000)
    )
    tiers_cfg = stats_cfg.get("benchmark_tiers", {}) or {}

    payload = base_report_envelope(
        schema=SCHEMA_VERSION,
        date=date,
        config_path=args.config,
        config_version=config.get("version", "unknown"),
    )
    payload.update(
        {
            "init_date": date,
            "tiers": {
                "tier_0_passive_index": _empty_tier(
                    tiers_cfg.get("tier_0_passive_index", "SPY+KOSPI200 50/50"),
                    initial_capital,
                ),
                "tier_1_mechanical": _empty_tier(
                    tiers_cfg.get("tier_1_mechanical", "score-only top-K, no LLM"),
                    initial_capital,
                ),
                "tier_2_llm_filtered": _empty_tier(
                    tiers_cfg.get("tier_2_llm_filtered", "system actual recommendations"),
                    initial_capital,
                ),
                "tier_3_random": _empty_tier(
                    tiers_cfg.get("tier_3_random", "random K from same A∩C universe"),
                    initial_capital,
                ),
            },
            "daily_snapshots": {},
            "warnings": [],
            "notes": [
                "본 state는 paper trade only. 실제 자본 이동 / broker 호출 없음 (G9).",
                "일별 갱신은 domains.audit_integrity.main 결정론 엔진 책임 (F-6).",
                "분기 비교는 investment-audit-outcome skill 책임.",
                "self_disable_trigger: tier_2 < tier_1 4 consecutive quarters → trigger 발동.",
            ],
        }
    )

    final = write_output_safely(out_path, payload)
    emit_summary_line(
        STAGE_NAME,
        {
            "date": date,
            "initial_capital_krw": initial_capital,
            "tiers": 4,
        },
        final,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
