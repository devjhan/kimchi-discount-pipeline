"""scan_catalysts — Stage 3 catalyst orchestrator (I/O 無).

detector fan-in → G15 d_type augment (cross-detector 집계는 detector 가 아니라 본
orchestrator 책임) → quality_pass marker → stats. 구 ``catalyst_scan.main`` 의
core 로직 (loading/envelope/write 제외) 이전.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from domains.catalyst.detectors.base import CatalystDetector, DetectContext
from domains.catalyst.domain.event import CatalystEvent


@dataclass(frozen=True)
class ScanResult:
    """scan_catalysts 산출 — envelope/write 제외한 substantive payload."""

    catalysts: tuple[CatalystEvent, ...]
    d_orphans: tuple[CatalystEvent, ...]
    stats: dict[str, Any]


def augment_d_type_into_primary(
    events: list[CatalystEvent],
) -> tuple[list[CatalystEvent], list[CatalystEvent]]:
    """d_type catalyst 를 같은 ticker 의 a/b primary trigger metadata 에 augment.

    primary trigger 가 없으면 d_type 단독 후보는 candidates 에서 제외 (G15) —
    별도 ``d_type_orphans`` list 로만 보존.
    """
    primary_by_ticker: dict[str, list[CatalystEvent]] = {}
    d_by_ticker: dict[str, list[CatalystEvent]] = {}
    for e in events:
        if e.trigger_class in ("a_type", "b_type"):
            primary_by_ticker.setdefault(e.ticker, []).append(e)
        elif e.trigger_class == "d_type":
            d_by_ticker.setdefault(e.ticker, []).append(e)
    primary_with_augment: list[CatalystEvent] = []
    d_orphans: list[CatalystEvent] = []
    for tkr, prims in primary_by_ticker.items():
        d_for_tkr = d_by_ticker.get(tkr, [])
        for p in prims:
            if d_for_tkr:
                p.metadata["d_type_augments"] = [
                    {
                        "catalyst_id": d.catalyst_id,
                        "catalyst_type": d.catalyst_type,
                        "source_citation": d.source_citation,
                    }
                    for d in d_for_tkr
                ]
            primary_with_augment.append(p)
    for tkr, ds in d_by_ticker.items():
        if tkr not in primary_by_ticker:
            for d in ds:
                d_orphans.append(d)
    return primary_with_augment, d_orphans


def scan_catalysts(
    *,
    detectors: Sequence[CatalystDetector],
    ctx: DetectContext,
    quality_pass: set[str],
    dry_run: bool,
) -> tuple[ScanResult, list[str]]:
    """enabled detector fan-in + augment + quality marker + stats.

    Returns:
        (ScanResult, detector_warnings) — detector_warnings 는 raw (secret redaction
        은 caller=main 책임, 구 catalyst_scan 의 warning 순서 보존).
    """
    detector_warnings: list[str] = []
    events: list[CatalystEvent] = []
    run_detection = (not dry_run) and bool(ctx.universe)
    if run_detection:
        for d in detectors:
            if not getattr(d, "enabled", True):
                continue
            res = d.detect(ctx)
            events.extend(res.events)
            detector_warnings.extend(res.warnings)

    catalysts, d_orphans = augment_d_type_into_primary(events)

    # quality 통과 안 한 ticker 도 후보에는 들어가되 marker 만 부여 (Stage 4 가 reject)
    for c in catalysts:
        if quality_pass and c.ticker not in quality_pass:
            c.metadata["quality_pass_at_stage2"] = False
        elif quality_pass:
            c.metadata["quality_pass_at_stage2"] = True
        else:
            c.metadata["quality_pass_at_stage2"] = "unknown_stage2_missing"

    by_type: dict[str, int] = {}
    for c in catalysts:
        by_type[c.catalyst_type] = by_type.get(c.catalyst_type, 0) + 1

    stats: dict[str, Any] = {
        "total_candidates": len(catalysts),
        "by_catalyst_type": by_type,
        "d_type_orphans_excluded": len(d_orphans),
        "universe_size": len(ctx.universe),
        "quality_pass_size": len(quality_pass),
        "dry_run": bool(dry_run),
    }
    return ScanResult(tuple(catalysts), tuple(d_orphans), stats), detector_warnings
