"""Stage 5b — Falsifier Proximity Monitor (measurement orchestration + IO).

F-8: 순수 분류 규칙 (`domain/proximity.py`) 위의 application layer. category dispatch /
citation 조립 / market_snapshot / positions 로드 / drift-{date}.md write 를 담당.
top-level `risk_engine/falsifier_proximity.py` 는 thin CLI delegator.

LLM 위임 절대 금지 (G6). 자동 청산 명령 절대 금지 (G9) — alert 산출만.
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

# ── Boundary-injected deps (D-ARCH-4 / ADR-0005, invariant-D) ───────────────────
# application/ 은 _boundary 를 import 하지 않는다. 플랫 shim
# (risk_engine/falsifier_proximity.py) 이 composition root 로서 configure(_boundary) 주입.
DEFAULT_ENV = DEFAULT_THRESHOLDS = KST = None
base_report_envelope = emit_summary_line = format_citation = None
load_env_file = load_yaml_config = normalize_to_trading_day = positions_store = None
secret_safe_log = write_output_safely = None
_positions_dir = _trail_dir = None


def configure(boundary: Any) -> None:
    """Composition-root wiring — 플랫 shim 이 _boundary 를 주입 (invariant-D 준수)."""
    g = globals()
    for _n in (
        "DEFAULT_ENV", "DEFAULT_THRESHOLDS", "KST", "base_report_envelope",
        "emit_summary_line", "format_citation", "load_env_file", "load_yaml_config",
        "normalize_to_trading_day", "positions_store", "secret_safe_log",
        "write_output_safely",
    ):
        g[_n] = getattr(boundary, _n)
    g["_positions_dir"] = boundary.resolve_positions_dir
    g["_trail_dir"] = boundary.resolve_trail_dir


from domains.risk_engine.domain.proximity import (  # noqa: E402
    DEFAULT_PROXIMITY_BANDS,
    ProximityRecord,
    classify as _classify,
    months_between as _months_between,
)

SCHEMA_VERSION = "investment-stage5b-falsifier-proximity-v1"
STAGE_NAME = "stage5b-falsifier-proximity"


def load_open_positions(positions_dir: Path) -> list[dict[str, Any]]:
    """$POSITIONS_DIR/{ticker}/thesis.json 을 모두 load (status='open' 만).

    스키마: ``telemetry/positions/README.md`` §3. 로더 로직(iterdir / corrupt-skip /
    status 필터)은 ``positions_store`` 로 단일화됨 — 본 함수는 thin wrapper.
    warnings 는 본 monitor 가 surface 하지 않으므로 drop (기존 거동 보존).
    """
    positions, _warnings = positions_store(positions_dir).load_open_raw()
    return positions


def measure_proximity(
    position: dict[str, Any],
    today: str,
    bands: dict[str, float],
    market_snapshot: dict[str, dict[str, Any]] | None = None,
) -> ProximityRecord:
    """
    한 position 의 proximity 산출.

    Args:
        position: load_open_positions() 단일 entry.
        today: KST YYYY-MM-DD.
        bands: thresholds.yaml.falsifier.proximity_bands.
        market_snapshot: {ticker: {"price_krw": float, "source": str, "ts": str}} 옵션.
                         metric_trigger.metric == 'price' 카테고리에 사용.
                         미제공 또는 ticker 미수록 시 metric_trigger 는 unmeasurable.

    Returns:
        ProximityRecord. raise 하지 않음 — 부적합 입력은 unmeasurable + rationale.
    """
    ticker = position.get("ticker") or "?"
    name = position.get("name") or ticker
    thesis = position.get("thesis") or {}
    falsifier = thesis.get("falsifier") or {}
    category = falsifier.get("category") or "unknown"
    spec = falsifier.get("spec") or {}

    if category == "time_cap":
        horizon = thesis.get("time_horizon_months")
        entry_date = position.get("entry_date")
        if not horizon or not entry_date:
            return ProximityRecord(
                ticker=ticker,
                name=name,
                proximity="unmeasurable",
                distance_ratio=None,
                rationale="time_cap: horizon 또는 entry_date 누락",
                falsifier_category=category,
                needs_user_decision=True,
            )
        try:
            elapsed = _months_between(str(entry_date), today)
            horizon_f = float(horizon)
        except (TypeError, ValueError):
            return ProximityRecord(
                ticker=ticker,
                name=name,
                proximity="unmeasurable",
                distance_ratio=None,
                rationale=f"time_cap: invalid horizon={horizon!r} or entry_date={entry_date!r}",
                falsifier_category=category,
                needs_user_decision=True,
            )
        if horizon_f <= 0:
            return ProximityRecord(
                ticker=ticker,
                name=name,
                proximity="unmeasurable",
                distance_ratio=None,
                rationale=f"time_cap: horizon={horizon_f} <= 0",
                falsifier_category=category,
                needs_user_decision=True,
            )
        ratio = max(0.0, 1.0 - elapsed / horizon_f)  # 1.0=entry, 0.0=발동
        prox = _classify(ratio, bands)
        return ProximityRecord(
            ticker=ticker,
            name=name,
            proximity=prox,
            distance_ratio=round(ratio, 4),
            rationale=(
                f"time_cap: {elapsed:.2f}개월 경과 / horizon {horizon_f:.1f}개월 "
                f"(잔여 {(horizon_f - elapsed):.2f}개월)"
            ),
            falsifier_category=category,
            citations=[
                format_citation(
                    "POSITION", f"{entry_date}->{today}", {"elapsed_months": elapsed}
                )
            ],
            needs_user_decision=(prox == "high"),
        )

    if category == "metric_trigger":
        metric = spec.get("metric")
        target = spec.get("target_value")
        baseline = spec.get("baseline_value", position.get("entry_price_krw"))
        direction = spec.get("direction", "below")  # 'below' | 'above'
        snap = (market_snapshot or {}).get(ticker) if market_snapshot else None
        if metric != "price" or snap is None or "price_krw" not in snap:
            return ProximityRecord(
                ticker=ticker,
                name=name,
                proximity="unmeasurable",
                distance_ratio=None,
                rationale=(
                    f"metric_trigger: 1차는 metric='price' 만 지원, market_snapshot 필요 "
                    f"(metric={metric!r}, snap_present={snap is not None})"
                ),
                falsifier_category=category,
                needs_user_decision=True,
            )
        try:
            current = float(snap["price_krw"])
            target_f = float(target)
            baseline_f = float(baseline)
        except (TypeError, ValueError):
            return ProximityRecord(
                ticker=ticker,
                name=name,
                proximity="unmeasurable",
                distance_ratio=None,
                rationale="metric_trigger: target/baseline/current numeric parse fail",
                falsifier_category=category,
                needs_user_decision=True,
            )
        denom = abs(baseline_f - target_f)
        if denom == 0:
            return ProximityRecord(
                ticker=ticker,
                name=name,
                proximity="unmeasurable",
                distance_ratio=None,
                rationale="metric_trigger: baseline == target (정의되지 않은 ratio)",
                falsifier_category=category,
                needs_user_decision=True,
            )
        # direction='below' → trigger when current <= target. distance ratio: |current - target| / denom (clamp 0~1)
        # direction='above' → trigger when current >= target. 대칭.
        gap = abs(current - target_f)
        ratio = max(0.0, min(1.0, gap / denom))
        # 단, 이미 trigger 방향을 넘었으면 distance=0 (proximity=high)
        if direction == "below" and current <= target_f:
            ratio = 0.0
        elif direction == "above" and current >= target_f:
            ratio = 0.0
        prox = _classify(ratio, bands)
        cite = format_citation(
            snap.get("source", "MARKET"),
            str(snap.get("ts", today)),
            {"price_krw": current, "target": target_f, "direction": direction},
        )
        return ProximityRecord(
            ticker=ticker,
            name=name,
            proximity=prox,
            distance_ratio=round(ratio, 4),
            rationale=(
                f"metric_trigger: 현재 {current:.0f}, target {target_f:.0f} ({direction}), "
                f"baseline {baseline_f:.0f}, gap_ratio {ratio:.3f}"
            ),
            falsifier_category=category,
            citations=[cite],
            needs_user_decision=(prox == "high"),
        )

    if category == "event_trigger":
        # event boolean — 본 helper 는 측정 불가. ingest_external_signal 또는
        # DART/뉴스 catalyst skill 이 별도 처리.
        return ProximityRecord(
            ticker=ticker,
            name=name,
            proximity="unmeasurable",
            distance_ratio=None,
            rationale=(
                "event_trigger: 본 helper 는 event boolean 판정 안 함. "
                "Stage 3 catalyst-scan 또는 /ingest-external-signal 산출물에서 별도 확인 필요."
            ),
            falsifier_category=category,
            needs_user_decision=False,  # 별도 채널이라 acknowledgement 미요구
        )

    return ProximityRecord(
        ticker=ticker,
        name=name,
        proximity="unmeasurable",
        distance_ratio=None,
        rationale=f"falsifier.category 미지정 또는 미지원 ({category!r})",
        falsifier_category=category,
        needs_user_decision=True,
    )


def render_drift_md(record: ProximityRecord, today: str) -> str:
    """drift-{date}.md 본문 렌더 (formatting only — 새 fact 추가 금지, G6/G7)."""
    lines: list[str] = []
    lines.append(f"# Falsifier Drift — {record.ticker} {record.name}  ({today})")
    lines.append("")
    lines.append(f"- proximity: **{record.proximity}**")
    if record.distance_ratio is not None:
        lines.append(
            f"- distance_ratio: {record.distance_ratio:.3f} "
            f"(1.0=entry 시점, 0.0=falsifier 발동)"
        )
    lines.append(f"- falsifier_category: {record.falsifier_category}")
    lines.append(f"- rationale: {record.rationale}")
    if record.needs_user_decision:
        lines.append("")
        lines.append(
            "> ⚠️ **needs_user_decision** — proximity 'high' 또는 측정 실패. "
            "사용자가 직접 thesis 재검토 필요."
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
        "모든 청산/재평가는 사용자 manual 결정."
    )
    lines.append("")
    return "\n".join(lines)


def _write_drift_md(positions_dir: Path, ticker: str, body: str) -> Path:
    """G20 — 같은 날 재실행 시 .{N}.md suffix 보존. ticker 안전 sanitize."""
    safe = ticker.replace(":", "_").replace("/", "_")
    sub = positions_dir / safe
    sub.mkdir(parents=True, exist_ok=True)
    today = datetime.now(KST).strftime("%Y-%m-%d")
    out = sub / f"drift-{today}.md"
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
    parser = argparse.ArgumentParser(description="Stage 5b — Falsifier Proximity Monitor")
    parser.add_argument("--date", help="YYYY-MM-DD (KST). 기본: 오늘")
    parser.add_argument("--config", default=str(DEFAULT_THRESHOLDS))
    parser.add_argument("--env", default=str(DEFAULT_ENV))
    parser.add_argument(
        "--trail-dir",
        default=None,
        help="output trail dir for summary JSON (default: TRAIL_TODAY)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="position 산출 없이 envelope 만 작성 (cron smoke test 용)",
    )
    args = parser.parse_args()

    config = load_yaml_config(args.config)
    env = load_env_file(args.env)
    date = normalize_to_trading_day(args.date)

    bands_cfg = (config.get("falsifier") or {}).get("proximity_bands") or {}
    bands = {
        "low_max": float(bands_cfg.get("low_max", DEFAULT_PROXIMITY_BANDS["low_max"])),
        "medium_max": float(
            bands_cfg.get("medium_max", DEFAULT_PROXIMITY_BANDS["medium_max"])
        ),
    }

    positions_dir = _positions_dir()
    all_warnings: list[str] = []

    if args.dry_run:
        records: list[ProximityRecord] = []
        all_warnings.append("--dry-run: positions scan skipped")
    else:
        positions = load_open_positions(positions_dir)
        records = []
        for pos in positions:
            try:
                rec = measure_proximity(pos, today=date, bands=bands)
            except Exception as exc:  # noqa: BLE001 — graceful per-position failure
                ticker = pos.get("ticker", "?")
                rec = ProximityRecord(
                    ticker=str(ticker),
                    name=str(pos.get("name", ticker)),
                    proximity="unmeasurable",
                    distance_ratio=None,
                    rationale=f"measure_proximity exception: {type(exc).__name__}: {exc}",
                    falsifier_category="error",
                    needs_user_decision=True,
                )
                all_warnings.append(secret_safe_log(rec.rationale, env))
            records.append(rec)
            body = render_drift_md(rec, today=date)
            _write_drift_md(positions_dir, rec.ticker, body)

    by_proximity: dict[str, int] = {}
    for r in records:
        by_proximity[r.proximity] = by_proximity.get(r.proximity, 0) + 1

    payload = base_report_envelope(
        schema=SCHEMA_VERSION,
        date=date,
        config_path=args.config,
        config_version=config.get("version", "unknown"),
    )
    payload.update(
        {
            "positions_dir": str(positions_dir),
            "proximity_bands": bands,
            "stats": {"total": len(records), "by_proximity": by_proximity},
            "records": [asdict(r) for r in records],
            "warnings": all_warnings,
        }
    )

    trail_dir = (
        Path(args.trail_dir) if args.trail_dir else _trail_dir(date)
    )
    out_path = trail_dir / "05b-falsifier-proximity.json"
    final = write_output_safely(out_path, payload)

    summary = {
        "date": date,
        "total": len(records),
        **{f"p_{k}": v for k, v in by_proximity.items()},
        "warnings": len(all_warnings),
    }
    emit_summary_line(STAGE_NAME, summary, final)
    return 0


if __name__ == "__main__":
    sys.exit(main())
