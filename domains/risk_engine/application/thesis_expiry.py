"""Stage 5d — Thesis Expiry Monitor (orchestration + IO).

F-8: 순수 tier 규칙 (`domain/expiry.py`) 위의 application layer. compute_expiry
(KST date 파싱 / citation 조립) · positions 로드 · expiry-{date}.md write · envelope.
top-level `risk_engine/thesis_expiry_monitor.py` 는 thin CLI delegator.

G6 (tier 분류 결정론) · G9 (alert 만, 자동 청산 금지) · G20 (덮어쓰기 금지).
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

# ── Boundary-injected deps (D-ARCH-4 / ADR-0005, invariant-D) ───────────────────
# application/ 은 _boundary 를 import 하지 않는다. 플랫 shim
# (risk_engine/thesis_expiry_monitor.py) 이 composition root 로서 configure(_boundary) 주입.
DEFAULT_THRESHOLDS = KST = base_report_envelope = emit_summary_line = None
format_citation = load_yaml_config = normalize_to_trading_day = positions_store = None
write_output_safely = None
_positions_dir = _trail_dir = None


def configure(boundary: Any) -> None:
    """Composition-root wiring — 플랫 shim 이 _boundary 를 주입 (invariant-D 준수)."""
    g = globals()
    for _n in (
        "DEFAULT_THRESHOLDS", "KST", "base_report_envelope", "emit_summary_line",
        "format_citation", "load_yaml_config", "normalize_to_trading_day",
        "positions_store", "write_output_safely",
    ):
        g[_n] = getattr(boundary, _n)
    g["_positions_dir"] = boundary.resolve_positions_dir
    g["_trail_dir"] = boundary.resolve_trail_dir


from domains.risk_engine.domain.expiry import (  # noqa: E402
    DAYS_PER_MONTH,
    DEFAULT_TIERS,
    ExpiryRecord,
    classify_tier as _classify_tier,
)

SCHEMA_VERSION = "investment-stage5d-thesis-expiry-v1"
STAGE_NAME = "stage5d-thesis-expiry"


def load_open_thesis(positions_dir: Path) -> tuple[list[dict[str, Any]], list[str]]:
    """$POSITIONS_DIR/{ticker}/thesis.json 모두 load. status='open' 만 반환.

    로더 로직은 ``positions_store`` 로 단일화됨 — 본 함수는 thin wrapper (warnings 보존).
    """
    return positions_store(positions_dir).load_open_raw()


def compute_expiry(
    position: dict[str, Any], today: str, tiers: dict[str, int]
) -> ExpiryRecord:
    ticker = position.get("ticker") or "?"
    name = position.get("name") or ticker
    thesis = position.get("thesis") or {}
    horizon = thesis.get("time_horizon_months")
    entry_date_raw = position.get("entry_date")

    if not horizon or not entry_date_raw:
        return ExpiryRecord(
            ticker=ticker,
            name=name,
            entry_date=str(entry_date_raw) if entry_date_raw else "?",
            horizon_months=0.0,
            expiry_date="?",
            days_remaining=0,
            tier="unmeasurable",
            rationale="time_horizon_months 또는 entry_date 누락",
            needs_user_decision=True,
        )

    try:
        entry_dt = datetime.strptime(str(entry_date_raw), "%Y-%m-%d").replace(
            tzinfo=KST
        )
        horizon_f = float(horizon)
        today_dt = datetime.strptime(today, "%Y-%m-%d").replace(tzinfo=KST)
    except (TypeError, ValueError) as exc:
        return ExpiryRecord(
            ticker=ticker,
            name=name,
            entry_date=str(entry_date_raw),
            horizon_months=0.0,
            expiry_date="?",
            days_remaining=0,
            tier="unmeasurable",
            rationale=f"date / horizon parse fail: {exc}",
            needs_user_decision=True,
        )

    if horizon_f <= 0:
        return ExpiryRecord(
            ticker=ticker,
            name=name,
            entry_date=str(entry_date_raw),
            horizon_months=horizon_f,
            expiry_date="?",
            days_remaining=0,
            tier="unmeasurable",
            rationale=f"horizon_months={horizon_f} <= 0",
            needs_user_decision=True,
        )

    expiry_dt = entry_dt + timedelta(days=horizon_f * DAYS_PER_MONTH)
    days_remaining = int((expiry_dt - today_dt).days)
    expiry_date = expiry_dt.strftime("%Y-%m-%d")

    tier = _classify_tier(days_remaining, tiers)
    needs_user_decision = tier in ("expired", "overdue", "warn")

    if tier == "expired":
        rationale = "thesis 만료 도래 — 오늘 (T-0). 사용자 재평가 필수."
    elif tier == "overdue":
        rationale = (
            f"thesis 만료 후 {abs(days_remaining)}일 경과 — 재평가 / 청산 / 연장 결정 필요"
        )
    elif tier == "warn":
        rationale = f"만료 임박 (잔여 {days_remaining}일, T-{days_remaining})"
    elif tier == "notice":
        rationale = f"만료 예고 (잔여 {days_remaining}일)"
    else:
        rationale = f"잔여 {days_remaining}일 — 만료 충분히 멀음"

    return ExpiryRecord(
        ticker=ticker,
        name=name,
        entry_date=str(entry_date_raw),
        horizon_months=round(horizon_f, 2),
        expiry_date=expiry_date,
        days_remaining=days_remaining,
        tier=tier,
        rationale=rationale,
        needs_user_decision=needs_user_decision,
        citations=[
            format_citation(
                "POSITION",
                str(entry_date_raw),
                {
                    "horizon_months": round(horizon_f, 2),
                    "expiry_date": expiry_date,
                    "days_remaining": days_remaining,
                },
            )
        ],
    )


def render_expiry_md(record: ExpiryRecord, today: str) -> str:
    """expiry-{date}.md 본문 렌더 (formatting only — G6/G7)."""
    tier_emoji = {
        "expired": "🛑",
        "overdue": "🛑",
        "warn":    "⚠️",
        "notice":  "ℹ️",
        "ok":      "✅",
        "unmeasurable": "❓",
    }.get(record.tier, "")

    lines: list[str] = []
    lines.append(f"# Thesis Expiry — {record.ticker} {record.name}  ({today})")
    lines.append("")
    lines.append(f"- tier: **{record.tier}** {tier_emoji}")
    lines.append(f"- entry_date: {record.entry_date}")
    lines.append(f"- horizon_months: {record.horizon_months}")
    lines.append(f"- expiry_date: {record.expiry_date}")
    lines.append(f"- days_remaining: {record.days_remaining}")
    lines.append(f"- rationale: {record.rationale}")
    if record.needs_user_decision:
        lines.append("")
        lines.append(
            "> ⚠️ **needs_user_decision** — thesis 재평가 / 청산 / horizon 연장 결정 필요."
        )
    if record.citations:
        lines.append("")
        lines.append("## Citations")
        for c in record.citations:
            lines.append(f"- `{c}`")
    lines.append("")
    lines.append("---")
    lines.append(
        "> 본 산출물은 자동 매매 명령이 아니다 (G9). "
        "모든 청산 / 재평가는 사용자 manual 결정."
    )
    lines.append("")
    return "\n".join(lines)


def _write_expiry_md(positions_dir: Path, ticker: str, body: str, today: str) -> Path:
    """G20 — 같은 날 재실행 시 .{N}.md suffix 보존."""
    safe = ticker.replace(":", "_").replace("/", "_")
    sub = positions_dir / safe
    sub.mkdir(parents=True, exist_ok=True)
    out = sub / f"expiry-{today}.md"
    final = out
    if final.exists():
        n = 1
        while True:
            cand = out.with_name(f"{out.stem}.{n}{out.suffix}")
            if not cand.exists():
                final = cand
                break
            n += 1
    final.write_text(body, encoding="utf-8")
    return final


def main() -> int:
    parser = argparse.ArgumentParser(description="Stage 5d — Thesis Expiry Monitor")
    parser.add_argument("--date", help="YYYY-MM-DD (KST). 기본: 오늘")
    parser.add_argument("--config", default=str(DEFAULT_THRESHOLDS))
    parser.add_argument(
        "--trail-dir",
        default=None,
        help="output trail dir for summary JSON (default: TRAIL_TODAY)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="positions scan 없이 envelope 만 작성 (cron smoke test 용)",
    )
    args = parser.parse_args()

    config = load_yaml_config(args.config)
    date = normalize_to_trading_day(args.date)

    tiers_cfg = (
        (config.get("thesis") or {})
        .get("expiry_alert", {})
        .get("tiers", {})
        or {}
    )
    tiers = {
        "notice_days":  int(tiers_cfg.get("notice_days",   DEFAULT_TIERS["notice_days"])),
        "warn_days":    int(tiers_cfg.get("warn_days",     DEFAULT_TIERS["warn_days"])),
        "expired_days": int(tiers_cfg.get("expired_days",  DEFAULT_TIERS["expired_days"])),
        "overdue_days": int(tiers_cfg.get("overdue_days",  DEFAULT_TIERS["overdue_days"])),
    }

    positions_dir = _positions_dir()
    all_warnings: list[str] = []
    records: list[ExpiryRecord] = []

    if args.dry_run:
        all_warnings.append("--dry-run: positions scan skipped")
    else:
        positions, pos_warnings = load_open_thesis(positions_dir)
        all_warnings.extend(pos_warnings)
        for pos in positions:
            try:
                rec = compute_expiry(pos, today=date, tiers=tiers)
            except Exception as exc:  # noqa: BLE001 — graceful per-position
                ticker = pos.get("ticker", "?")
                rec = ExpiryRecord(
                    ticker=str(ticker),
                    name=str(pos.get("name", ticker)),
                    entry_date=str(pos.get("entry_date", "?")),
                    horizon_months=0.0,
                    expiry_date="?",
                    days_remaining=0,
                    tier="unmeasurable",
                    rationale=f"compute_expiry exception: {type(exc).__name__}: {exc}",
                    needs_user_decision=True,
                )
                all_warnings.append(rec.rationale)
            records.append(rec)
            body = render_expiry_md(rec, today=date)
            _write_expiry_md(positions_dir, rec.ticker, body, today=date)

    by_tier: dict[str, int] = {}
    for r in records:
        by_tier[r.tier] = by_tier.get(r.tier, 0) + 1

    payload = base_report_envelope(
        schema=SCHEMA_VERSION,
        date=date,
        config_path=args.config,
        config_version=config.get("version", "unknown"),
    )
    payload.update(
        {
            "positions_dir": str(positions_dir),
            "tiers": tiers,
            "stats": {"total": len(records), "by_tier": by_tier},
            "records": [asdict(r) for r in records],
            "warnings": all_warnings,
        }
    )

    trail_dir = (
        Path(args.trail_dir) if args.trail_dir else _trail_dir(date)
    )
    trail_dir.mkdir(parents=True, exist_ok=True)
    out_path = trail_dir / "05d-thesis-expiry.json"
    final = write_output_safely(out_path, payload)

    summary = {
        "date": date,
        "total": len(records),
        **{f"t_{k}": v for k, v in by_tier.items()},
        "needs_decision": sum(1 for r in records if r.needs_user_decision),
        "warnings": len(all_warnings),
    }
    emit_summary_line(STAGE_NAME, summary, final)
    return 0


if __name__ == "__main__":
    sys.exit(main())
