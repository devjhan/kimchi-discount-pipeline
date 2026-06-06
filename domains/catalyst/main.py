"""catalyst CLI entry — Stage 3 Catalyst Event Scan (구 3 CLI step → 1 step).

usage:
    python -m domains.catalyst.main --date 2026-05-17
    python -m domains.catalyst.main --dry-run
    python -m domains.catalyst.main --trail-dir /custom/dir

산출물: ``$TRAIL_TODAY/03-catalyst-events.json`` (envelope schema
``investment-stage3-catalyst-events-v1`` — 구 ``alpha_factory.catalyst_scan`` 와 호환).
구 중간 산출물 (03-index-deletion.json / 03-earnings-panic.json) 은 detector io 로
흡수되어 더 이상 생성되지 않는다.

Hard guards: G6 (deterministic threshold) / G7 (source citation) / G8 (source 미가용
graceful) / G14 (universe 외 ticker 금지) / G15 (d_type 단독 trigger 금지) / G20 (G20 writer).
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import asdict
from datetime import date as _date
from pathlib import Path

from domains._shared.time.clock import AsOfClock
from domains.catalyst import _boundary
from domains.catalyst.application.scan_catalysts import scan_catalysts
from domains.catalyst.audit.log import ViolationLog
from domains.catalyst.audit.violation import GuardViolation
from domains.catalyst.detectors.base import DetectContext
from domains.catalyst.detectors.factory import build_detectors
from domains.catalyst.io.trail_loader import (
    load_quality_pass,
    load_universe_market,
    load_universe_tickers,
)

SCHEMA_VERSION = "investment-stage3-catalyst-events-v1"
STAGE_NAME = "stage3-catalyst-scan"
_DETECTORS_CONFIG_FILENAME = "detectors.yaml"

_UNIVERSE_EMPTY_WARN = (
    "Stage 1 universe empty/missing — Stage 3 catalyst scan은 universe 의존. "
    "Stage 1 cron run 후 재실행 권고."
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="domains.catalyst.main",
        description="Stage 3 — Catalyst Event Scan (6 detector fan-in + G15 d_type augment).",
    )
    parser.add_argument("--date", help="YYYY-MM-DD (KST). 기본: 오늘 거래일.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="universe / quality 파일만 read, detector 외부 IO skip.",
    )
    parser.add_argument(
        "--trail-dir",
        default=None,
        help="output trail dir override. 기본: $TRAIL_TODAY env, else operations/{KST 거래일}.",
    )
    parser.add_argument(
        "--allow-yahoo-fallback",
        action="store_true",
        default=None,
        help="KIS 미가용 시 Yahoo 사용 (CLI 명시 시 True override; "
        "미명시 시 config/user/behavior.yaml 결정).",
    )
    args = parser.parse_args(argv)

    date = _boundary.normalize_to_trading_day(args.date)
    fetched_at = _boundary.now_iso_kst()
    clock = AsOfClock.at_market_close(_date.fromisoformat(date))
    violation_log = ViolationLog(clock)

    # ----- config / env -----
    detectors_cfg = _boundary.load_detectors_config()
    env: dict[str, str] = {} if args.dry_run else _boundary.load_env()
    if not env and not args.dry_run:
        print(
            f"[{STAGE_NAME}] WARN: .env 로드 실패 — DART/KIS fetch skip 됨",
            file=sys.stderr,
        )

    # ----- detectors build (config 오류 → blocking + exit 2) -----
    try:
        detectors = build_detectors(detectors_cfg.get("detectors") or [])
    except ValueError as exc:
        violation_log.record(
            GuardViolation(
                detected_at=_boundary.now_kst(),
                severity="blocking",
                rule_name="config_build",
                ticker=None,
                message=str(exc),
                context={"config": _DETECTORS_CONFIG_FILENAME},
            )
        )
        print(f"[{STAGE_NAME}] config build blocked: {exc}", file=sys.stderr)
        return 2

    # ----- load Stage 1/2 산출물 + warning 순서 보존 -----
    all_warnings: list[str] = []
    universe, uni_warns = load_universe_tickers(date)
    for w in uni_warns:
        all_warnings.append(_boundary.secret_safe_log(w, env))
    if not universe:
        all_warnings.append(_UNIVERSE_EMPTY_WARN)

    quality_pass, qual_warns = load_quality_pass(date)
    for w in qual_warns:
        all_warnings.append(_boundary.secret_safe_log(w, env))

    universe_market = {} if args.dry_run else load_universe_market(date)
    allow_yahoo = _boundary.resolve_allow_yahoo_fallback(args.allow_yahoo_fallback)

    ctx = DetectContext(
        env=env,
        universe=universe,
        universe_market=universe_market,
        date=date,
        fetched_at=fetched_at,
        allow_yahoo=allow_yahoo,
    )

    # ----- orchestrate (detector fan-in + augment + quality marker + stats) -----
    result, detector_warnings = scan_catalysts(
        detectors=detectors,
        ctx=ctx,
        quality_pass=quality_pass,
        dry_run=args.dry_run,
    )
    for w in detector_warnings:
        all_warnings.append(_boundary.secret_safe_log(w, env))
    if args.dry_run:
        all_warnings.append("--dry-run: catalyst detection skipped")

    # ----- envelope build -----
    payload = _boundary.base_report_envelope(
        schema=SCHEMA_VERSION,
        date=date,
        config_path=str(_boundary.config_path(_DETECTORS_CONFIG_FILENAME)),
        config_version=detectors_cfg.get("version", "unknown"),
    )
    payload.update(
        {
            "stats": result.stats,
            "catalysts": [asdict(c) for c in result.catalysts],
            "d_type_orphans": [asdict(c) for c in result.d_orphans],
            "warnings": all_warnings,
        }
    )

    # ----- write trail -----
    trail_dir = Path(args.trail_dir) if args.trail_dir else _boundary.resolve_trail_dir(date)
    trail_dir.mkdir(parents=True, exist_ok=True)
    out_path = trail_dir / "03-catalyst-events.json"
    final = _boundary.write_output_safely(out_path, payload)

    _boundary.emit_summary(
        STAGE_NAME,
        {
            "date": date,
            "candidates": len(result.catalysts),
            "d_orphans": len(result.d_orphans),
            "universe": len(universe),
            "quality_pass": len(quality_pass),
            "warnings": len(all_warnings),
        },
        final,
    )
    return 2 if violation_log.has_blocking else 0


if __name__ == "__main__":
    sys.exit(main())
