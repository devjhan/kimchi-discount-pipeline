"""Stage 5c — Event Falsifier Linker (cross-reference orchestration + IO).

F-8: 순수 value object + index (`domain/event_trigger.py`) 위의 application layer.
event_trigger falsifier 를 Stage 3 catalyst-scan 산출물과 deterministic cross-reference.
top-level `risk_engine/event_falsifier_linker.py` 는 thin CLI delegator.

Hard guards: G6 (순수 JSON lookup, LLM inference 금지) · G7 (Stage 3 citation 직접 인용)
· G8 (Stage 3 파일 미존재 graceful) · G9 (alert 만) · G20.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

# ── Boundary-injected deps (D-ARCH-4 / ADR-0005, invariant-D) ───────────────────
# application/ 은 _boundary 를 import 하지 않는다. 플랫 shim
# (risk_engine/event_falsifier_linker.py) 이 composition root 로서 configure(_boundary) 주입.
DEFAULT_ENV = DEFAULT_THRESHOLDS = base_report_envelope = emit_summary_line = None
format_citation = load_env_file = load_yaml_config = normalize_to_trading_day = None
positions_store = secret_safe_log = write_output_safely = None
_positions_dir = _trail_dir = None


def configure(boundary: Any) -> None:
    """Composition-root wiring — 플랫 shim 이 _boundary 를 주입 (invariant-D 준수)."""
    g = globals()
    for _n in (
        "DEFAULT_ENV", "DEFAULT_THRESHOLDS", "base_report_envelope", "emit_summary_line",
        "format_citation", "load_env_file", "load_yaml_config", "normalize_to_trading_day",
        "positions_store", "secret_safe_log", "write_output_safely",
    ):
        g[_n] = getattr(boundary, _n)
    g["_positions_dir"] = boundary.resolve_positions_dir
    g["_trail_dir"] = boundary.resolve_trail_dir


from domains.risk_engine.domain.event_trigger import (
    EventTriggerStatus,
    build_stage3_index as _build_stage3_index,
)

SCHEMA_VERSION = "investment-stage5c-event-falsifier-linker-v1"
STAGE_NAME = "stage5c-event-falsifier-linker"
OUTPUT_FILENAME_PREFIX = "event-trigger-status"

# Stage 3 output filename convention
STAGE3_FILENAME = "03-catalyst-events.json"


# ============================================================
# I/O helpers
# ============================================================

def load_event_trigger_positions(
    positions_dir: Path,
) -> tuple[list[dict[str, Any]], list[str]]:
    """$POSITIONS_DIR/{ticker}/thesis.json 전부 load.
    status='open' + falsifier.category == 'event_trigger' 인 것만 반환.

    로더 로직은 ``positions_store`` 로 단일화됨 — 본 함수는 thin wrapper(category 필터).
    """
    return positions_store(positions_dir).load_open_raw(category="event_trigger")


def load_stage3_catalysts(
    trail_dir: Path,
) -> tuple[list[dict[str, Any]], list[str]]:
    """
    $TRAIL_TODAY/03-catalyst-events.json load.
    catalysts + d_type_orphans 를 flat list로 반환.
    미존재 / parse 실패 → ([], [warning]) (G8 — abort 않음).
    """
    warnings: list[str] = []
    p = trail_dir / STAGE3_FILENAME
    if not p.exists():
        warnings.append(
            f"Stage 3 산출물 없음: {p}. "
            "오늘 Stage 3 미실행 또는 trail_dir 불일치. "
            "event_trigger 전 종목 → signal=unspecified."
        )
        return [], warnings
    try:
        with p.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        warnings.append(f"Stage 3 JSON parse 실패: {p} — {exc} (G8)")
        return [], warnings

    catalysts = list(data.get("catalysts") or [])
    orphans = list(data.get("d_type_orphans") or [])
    return catalysts + orphans, warnings


# ============================================================
# Core evaluation (G6 — pure JSON lookup, no inference)
# ============================================================

def evaluate_position(
    position: dict[str, Any],
    stage3_by_ticker: dict[str, list[dict[str, Any]]],
    today: str,
) -> EventTriggerStatus:
    """
    단일 position의 event_trigger falsifier를 Stage 3 index와 cross-reference.

    G6: 순수 JSON lookup. LLM inference 없음.

    Signal 결정 매트릭스:
        direction=presence  + seen_today=True   → triggered
        direction=presence  + seen_today=False  → not_triggered
        direction=absence   + seen_today=False  → triggered
        direction=absence   + seen_today=True   → not_triggered
        watch_catalyst_type 미지정 또는 direction=unspecified → unspecified
    """
    ticker = position.get("ticker") or "?"
    name = position.get("name") or ticker
    thesis = position.get("thesis") or {}
    spec = (thesis.get("falsifier") or {}).get("spec") or {}

    description = (
        spec.get("description")
        or spec.get("event_pattern")
        or "(falsifier description 없음 — spec.description 추가 권장)"
    )
    watch_catalyst_type: str | None = spec.get("watch_catalyst_type")
    direction: str = spec.get("direction", "unspecified")

    # Stage 3 match: ticker + (optionally) catalyst_type
    ticker_catalysts = stage3_by_ticker.get(ticker, [])
    if watch_catalyst_type is not None:
        stage3_matches = [
            c for c in ticker_catalysts
            if c.get("catalyst_type") == watch_catalyst_type
        ]
        seen_today: bool | None = bool(stage3_matches)
    else:
        stage3_matches = ticker_catalysts
        seen_today = None

    # signal determination
    if seen_today is None or direction == "unspecified":
        signal = "unspecified"
        needs_user_decision = True
        rationale = (
            f"event_trigger: watch_catalyst_type={'미지정' if watch_catalyst_type is None else watch_catalyst_type!r}, "
            f"direction={direction!r}. "
            "spec.watch_catalyst_type + spec.direction 추가 후 자동 판정 가능."
        )
    elif direction == "presence":
        signal = "triggered" if seen_today else "not_triggered"
        needs_user_decision = (signal == "triggered")
        rationale = (
            f"direction=presence, watch_catalyst_type={watch_catalyst_type!r}, "
            f"Stage 3 matches today: {len(stage3_matches)}건 → {signal}"
        )
    elif direction == "absence":
        signal = "triggered" if not seen_today else "not_triggered"
        needs_user_decision = (signal == "triggered")
        rationale = (
            f"direction=absence, watch_catalyst_type={watch_catalyst_type!r}, "
            f"Stage 3 matches today: {len(stage3_matches)}건 → {signal}"
        )
    else:
        signal = "unspecified"
        needs_user_decision = True
        rationale = f"direction={direction!r} 미지원 값 (presence | absence 만 허용)"

    # G7: source citations from Stage 3 entries
    citations: list[str] = []
    for m in stage3_matches:
        raw_cite = m.get("source_citation")
        if raw_cite:
            citations.append(str(raw_cite))
    citations.append(
        format_citation(
            "POSITION",
            today,
            {"ticker": ticker, "watch_catalyst_type": watch_catalyst_type, "direction": direction},
        )
    )

    return EventTriggerStatus(
        ticker=ticker,
        name=name,
        falsifier_description=description,
        watch_catalyst_type=watch_catalyst_type,
        direction=direction,
        stage3_matches=stage3_matches,
        seen_today=seen_today,
        signal=signal,
        rationale=rationale,
        source_citations=citations,
        needs_user_decision=needs_user_decision,
    )


# ============================================================
# main
# ============================================================

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Stage 5c — Event Falsifier Linker")
    parser.add_argument("--date", help="YYYY-MM-DD (KST). 기본: 오늘")
    parser.add_argument("--config", default=str(DEFAULT_THRESHOLDS))
    parser.add_argument("--env", default=str(DEFAULT_ENV))
    parser.add_argument(
        "--trail-dir",
        default=None,
        help="trail 디렉토리 (기본: 오늘 KST 거래일 operations/{date})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="positions scan 없이 빈 envelope만 작성 (smoke test용)",
    )
    args = parser.parse_args(argv)

    config = load_yaml_config(args.config)
    env = load_env_file(args.env)
    date = normalize_to_trading_day(args.date)

    positions_dir = _positions_dir()
    trail_dir = Path(args.trail_dir) if args.trail_dir else _trail_dir()

    all_warnings: list[str] = []
    records: list[EventTriggerStatus] = []

    if args.dry_run:
        all_warnings.append("--dry-run: positions scan skipped")
    else:
        positions, pos_warnings = load_event_trigger_positions(positions_dir)
        all_warnings.extend(pos_warnings)

        catalysts, cat_warnings = load_stage3_catalysts(trail_dir)
        all_warnings.extend(cat_warnings)

        stage3_index = _build_stage3_index(catalysts)

        for pos in positions:
            try:
                rec = evaluate_position(pos, stage3_index, date)
            except Exception as exc:  # noqa: BLE001 — graceful per-position failure
                ticker = pos.get("ticker", "?")
                w = f"evaluate_position exception {ticker}: {type(exc).__name__}: {exc}"
                all_warnings.append(secret_safe_log(w, env))
                rec = EventTriggerStatus(
                    ticker=str(ticker),
                    name=str(pos.get("name", ticker)),
                    falsifier_description="(evaluation error)",
                    watch_catalyst_type=None,
                    direction="unspecified",
                    stage3_matches=[],
                    seen_today=None,
                    signal="unspecified",
                    rationale=w,
                    source_citations=[],
                    needs_user_decision=True,
                )
            records.append(rec)

    # Stats
    stats: dict[str, int] = {
        "total_event_trigger_positions": len(records),
        "triggered": sum(1 for r in records if r.signal == "triggered"),
        "not_triggered": sum(1 for r in records if r.signal == "not_triggered"),
        "unspecified": sum(1 for r in records if r.signal == "unspecified"),
        "needs_user_decision": sum(1 for r in records if r.needs_user_decision),
    }

    config_version = (config.get("_meta") or {}).get("version", "unknown")
    envelope = base_report_envelope(
        schema=SCHEMA_VERSION,
        date=date,
        config_path=args.config,
        config_version=config_version,
    )
    envelope["stats"] = stats
    envelope["records"] = [asdict(r) for r in records]
    envelope["warnings"] = [secret_safe_log(w, env) for w in all_warnings]

    out_path = trail_dir / f"{OUTPUT_FILENAME_PREFIX}-{date}.json"
    final_path = write_output_safely(out_path, envelope)
    emit_summary_line(
        STAGE_NAME,
        {
            "total": stats["total_event_trigger_positions"],
            "triggered": stats["triggered"],
            "unspecified": stats["unspecified"],
            "needs_user_decision": stats["needs_user_decision"],
        },
        final_path,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
