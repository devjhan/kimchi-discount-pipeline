"""Portfolio drawdown / cash% derive — orchestration + IO.

F-8: 순수 산식 + value object (`domain/portfolio_state.py`) 위의 application layer.
positions_sync 의 `_summary-{date}.json` 누적분 scan / citation 조립 / `_derived-{date}.json`
write. top-level `risk_engine/portfolio_state_derive.py` 는 thin CLI delegator.

Hard guards: G7 (citation) · G8 (summary 0개 → skip_reason) · G9 (read-only) · G20.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from domains.risk_engine._boundary import (
    KST,
    base_report_envelope,
    emit_summary_line,
    format_citation,
    load_derived_state,
    normalize_to_trading_day,
    resolve_positions_dir as _positions_dir,
    write_output_safely,
)
from domains.risk_engine.domain.portfolio_state import (
    DEFAULT_LOOKBACK_DAYS,
    SCHEMA_VERSION,
    DerivedState,
    compute_cash_pct,
    compute_drawdown_pct,
)

STAGE_NAME = "portfolio-state-derive"


def _summary_file(positions_dir: Path, date: str) -> Path:
    return positions_dir / f"_summary-{date}.json"


def _load_summary(p: Path) -> dict[str, Any] | None:
    if not p.exists():
        return None
    try:
        with p.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None
    return (data or {}).get("payload") or data


def _enumerate_summary_dates(
    positions_dir: Path, end_date: str, lookback_days: int
) -> list[tuple[str, Path]]:
    """end_date 기준 과거 lookback_days 일치 _summary-YYYY-MM-DD.json 들을 enumerate.

    파일 미존재 일자는 skip — 모든 거래일에 sync 실행이 안 됐을 수 있음.
    """
    end_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(tzinfo=KST)
    out: list[tuple[str, Path]] = []
    for offset in range(0, lookback_days + 1):
        d = (end_dt - timedelta(days=offset)).strftime("%Y-%m-%d")
        p = _summary_file(positions_dir, d)
        if p.exists():
            out.append((d, p))
    return out


def derive_state(
    *,
    positions_dir: Path,
    date: str,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
) -> DerivedState:
    """positions_sync history → DerivedState. graceful per G8."""
    state = DerivedState(date=date, lookback_days=lookback_days)

    summaries = _enumerate_summary_dates(positions_dir, date, lookback_days)
    state.summaries_scanned = len(summaries)

    if not summaries:
        state.skip_reason = (
            "no positions_sync summary files found "
            f"(scanned {date} ↓ {lookback_days}d). "
            "Run domains.risk_engine.positions_sync first."
        )
        return state

    # peak across all summaries
    peak_value: float | None = None
    peak_date: str | None = None
    for d, p in summaries:
        payload = _load_summary(p)
        if not payload:
            state.warnings.append(f"summary parse fail: {p.name}")
            continue
        ta = payload.get("total_assets_krw")
        if isinstance(ta, (int, float)) and ta > 0:
            if peak_value is None or ta > peak_value:
                peak_value = float(ta)
                peak_date = d

    state.peak_total_assets_krw = peak_value
    state.peak_observed_at = peak_date

    # current = most recent summary (summaries[0] since enumerate ordered offset 0..N)
    current_d, current_p = summaries[0]
    current_payload = _load_summary(current_p)
    if not current_payload:
        state.skip_reason = (
            f"current summary parse fail: {current_p.name} — abort derive"
        )
        return state

    ta_current = current_payload.get("total_assets_krw")
    cash_current = current_payload.get("cash_krw")

    if isinstance(ta_current, (int, float)) and ta_current > 0:
        state.current_total_assets_krw = float(ta_current)
        state.source_citations.append(
            format_citation(
                "POSITIONS", current_d, {"total_assets_krw": float(ta_current)}
            )
        )
    if isinstance(cash_current, (int, float)) and cash_current >= 0:
        state.current_cash_krw = float(cash_current)
        state.source_citations.append(
            format_citation(
                "POSITIONS", current_d, {"cash_krw": float(cash_current)}
            )
        )

    # drawdown / cash% — 순수 산식 (domain)
    state.current_drawdown_pct = compute_drawdown_pct(
        peak_value, state.current_total_assets_krw
    )
    state.current_cash_pct = compute_cash_pct(
        state.current_cash_krw, state.current_total_assets_krw
    )

    if peak_date is not None:
        state.source_citations.append(
            format_citation(
                "POSITIONS",
                peak_date,
                {"peak_total_assets_krw": peak_value},
            )
        )

    return state


def load_derived(positions_dir: Path, date: str) -> dict[str, Any] | None:
    """sizing.py / 타 helper 의 fallback read.

    read 로직은 ``_boundary.load_derived_state`` 로 단일화 — 본 함수는 signature 보존
    wrapper. 파일 미존재 / parse 실패 시 None (caller graceful skip).
    """
    return load_derived_state(date, positions_dir=positions_dir)


def main() -> int:
    parser = argparse.ArgumentParser(description="Portfolio drawdown / cash% derive")
    parser.add_argument("--date", default=None, help="YYYY-MM-DD (default: today KST)")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="positions scan 없이 envelope 만 산출",
    )
    parser.add_argument(
        "--lookback-days",
        type=int,
        default=DEFAULT_LOOKBACK_DAYS,
        help=f"peak 추적 lookback 일수 (default: {DEFAULT_LOOKBACK_DAYS})",
    )
    parser.add_argument(
        "--trail-dir",
        default=None,
        help="(unused — 본 helper 는 _positions/ 에 직접 write)",
    )
    args = parser.parse_args()

    date = normalize_to_trading_day(args.date)
    positions_dir = _positions_dir()

    if args.dry_run:
        emit_summary_line(
            STAGE_NAME,
            {
                "stage": STAGE_NAME,
                "date": date,
                "dry_run": True,
                "positions_dir": str(positions_dir),
            },
            Path("/dev/null"),
        )
        return 0

    state = derive_state(
        positions_dir=positions_dir, date=date, lookback_days=args.lookback_days
    )

    envelope = base_report_envelope(
        schema=SCHEMA_VERSION,
        date=date,
        config_path=str(positions_dir),
        config_version=1,
    )
    envelope["payload"] = asdict(state)

    out_path = positions_dir / f"_derived-{date}.json"
    final = write_output_safely(out_path, envelope)

    emit_summary_line(
        STAGE_NAME,
        {
            "date": date,
            "summaries_scanned": state.summaries_scanned,
            "peak_total_assets_krw": state.peak_total_assets_krw,
            "current_drawdown_pct": state.current_drawdown_pct,
            "current_cash_pct": state.current_cash_pct,
            "skip_reason": state.skip_reason,
        },
        final,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
