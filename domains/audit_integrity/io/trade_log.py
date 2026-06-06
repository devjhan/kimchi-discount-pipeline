"""Trade-log CSV writer — tier 별 closed trade append.

``$AUDIT_DIR/trade-log-{tier}.csv`` append-only. columns:
trade_id,ticker,entry_date,entry_price_krw,exit_date,exit_price_krw,return_pct,reason.
새 파일이면 header 부터 기록.
"""
from __future__ import annotations

import csv
from pathlib import Path

from domains.audit_integrity import _boundary
from domains.audit_integrity.domain.state import ClosedTrade

_HEADER = (
    "trade_id",
    "ticker",
    "entry_date",
    "entry_price_krw",
    "exit_date",
    "exit_price_krw",
    "return_pct",
    "reason",
)


def append_closed_trades(trades: list[ClosedTrade]) -> list[Path]:
    """tier 별로 그룹화해 trade-log-{tier}.csv 에 append. 기록된 파일 경로 list 반환."""
    audit_dir = _boundary.resolve_path("operations_audit")
    audit_dir.mkdir(parents=True, exist_ok=True)
    by_tier: dict[str, list[ClosedTrade]] = {}
    for t in trades:
        by_tier.setdefault(t.tier, []).append(t)

    written: list[Path] = []
    for tier_key, tier_trades in by_tier.items():
        path = audit_dir / f"trade-log-{tier_key}.csv"
        new_file = not path.exists()
        with path.open("a", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            if new_file:
                w.writerow(_HEADER)
            for t in tier_trades:
                w.writerow(
                    [
                        t.trade_id,
                        t.ticker,
                        t.entry_date,
                        t.entry_price_krw,
                        t.exit_date,
                        t.exit_price_krw,
                        t.return_pct,
                        t.reason,
                    ]
                )
        written.append(path)
    return written
