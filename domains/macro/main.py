"""macro CLI entry — Stage 0 macro regime classifier.

usage:
    python -m domains.macro.main --date 2026-05-17
    python -m domains.macro.main --dry-run

산출물: ``$TRAIL_TODAY/00-macro-regime.json`` (envelope schema
``investment-stage0-macro-regime-v1`` — legacy ``risk_engine.macro_regime`` 와 호환).
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import asdict
from datetime import date as _date
from datetime import datetime
from pathlib import Path
from typing import Any

from domains._shared.time.clock import AsOfClock
from domains.macro import _boundary
from domains.macro.application.regime_classify import classify_regime, detect_regime_shift
from domains.macro.audit.citation import is_valid_citation
from domains.macro.audit.log import ViolationLog
from domains.macro.audit.violation import GuardViolation
from domains.macro.domain.regime import IndicatorResult
from domains.macro.signals.base import empty_indicator
from domains.macro.signals.factory import build_signals

SCHEMA_VERSION = "investment-stage0-macro-regime-v1"
STAGE_NAME = "stage0-macro-regime"


def _parse_date(s: str | None) -> _date:
    if s:
        return datetime.strptime(s, "%Y-%m-%d").date()
    return _boundary.now_kst().date()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="domains.macro.main",
        description="Stage 0 — Macro regime classifier (4 indicator → regime label + cash_band).",
    )
    parser.add_argument("--date", help="YYYY-MM-DD (KST). 기본: 오늘 거래일.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="indicator API 호출 skip → 모든 indicator skip + regime=unknown",
    )
    parser.add_argument(
        "--trail-dir",
        default=None,
        help="output trail dir override. 기본: $TRAIL_TODAY.",
    )
    args = parser.parse_args(argv)

    target_date = _parse_date(args.date)
    clock = AsOfClock.at_market_close(target_date)
    date_iso = clock.trading_date.isoformat()

    violation_log = ViolationLog(clock)

    # ----- config 로드 -----
    cfg = _boundary.load_regimes_config()
    env = _boundary.load_env() if not args.dry_run else {}

    # ----- indicator collection (config signals: 순서대로 fetch) -----
    signals = build_signals(cfg)
    all_warnings: list[str] = []
    indicators: dict[str, IndicatorResult] = {}

    if args.dry_run:
        all_warnings.append("--dry-run: indicator API 호출 skip → regime=unknown")
        for sig in signals:
            indicators[sig.name] = empty_indicator("--dry-run")
    else:
        for sig in signals:
            ind, warns = sig.fetch(env, date_iso)
            indicators[sig.name] = ind
            for w in warns:
                all_warnings.append(_boundary.secret_safe_log(w, env))

    # ----- classify + cash_band + shift -----
    decision = classify_regime(indicators, cfg)
    cash_band = (cfg.get("cash_band") or {}).get(decision.regime, [0.30, 0.70])
    total_exposure_budget = round(1.0 - cash_band[1], 4)
    # composition root: trail 경로 resolver 주입 (application 은 _boundary 비의존 — ADR-0005)
    shift = detect_regime_shift(
        date_iso,
        decision.regime,
        cfg,
        trail_dir_for=lambda d: _boundary.resolve_path("trail_today", date=d),
    )

    # ----- runtime invariants — G7 citation 검증 -----
    for name, ind in indicators.items():
        if ind.source_citation and not is_valid_citation(ind.source_citation):
            violation_log.record(
                GuardViolation(
                    detected_at=_boundary.now_kst(),
                    severity="warning",
                    rule_name="g7_citation_format",
                    ticker=None,
                    message=f"indicator '{name}' malformed citation: {ind.source_citation!r}",
                    context={"indicator": name},
                )
            )

    # ----- envelope build (legacy schema 호환) -----
    envelope = _boundary.base_report_envelope(
        schema=SCHEMA_VERSION,
        date=date_iso,
        config_path=str(_boundary.config_path("regimes.yaml")),
        config_version=cfg.get("version", "unknown"),
    )
    envelope.update(
        {
            "regime_decision": {
                "regime": decision.regime,
                "rationale": list(decision.rationale),
                "votes": list(decision.votes),
                "vote_summary": decision.vote_summary,
            },
            "cash_band": list(cash_band),
            "total_exposure_budget": total_exposure_budget,
            "indicators": {name: _serialize_indicator(ind) for name, ind in indicators.items()},
            "regime_shift": shift,
            "warnings": all_warnings,
        }
    )

    # ----- write trail -----
    trail_dir = Path(args.trail_dir) if args.trail_dir else _boundary.resolve_trail_dir(date_iso)
    trail_dir.mkdir(parents=True, exist_ok=True)
    out_path = trail_dir / "00-macro-regime.json"
    final = _boundary.write_output_safely(out_path, envelope)

    # ----- handoff summary -----
    _boundary.emit_summary(
        STAGE_NAME,
        {
            "date": date_iso,
            "regime": decision.regime,
            "cash_band": f"{cash_band[0]:.2f}-{cash_band[1]:.2f}",
            "shift_alert": shift["alert"],
            "warnings": len(all_warnings),
            "mode": "dry-run" if args.dry_run else "live",
        },
        final,
    )

    return 2 if violation_log.has_blocking else 0


def _serialize_indicator(ind: IndicatorResult) -> dict[str, Any]:
    """legacy schema 호환 — IndicatorResult → dict (envelope.indicators[name] 값)."""
    d = asdict(ind)
    # legacy 는 percentile=None 일 때 key 자체를 생략 → 동일 행동
    if d.get("percentile") is None:
        d.pop("percentile", None)
    if d.get("skip_reason") is None:
        d.pop("skip_reason", None)
    return d


if __name__ == "__main__":
    sys.exit(main())
