"""Stage 5a — Thesis Sync (thesis.json writer) — assembly + IO.

F-8: 순수 projection 규칙 (`domain/thesis_projection.py`) 위의 application layer.
``project_thesis`` (now_iso_kst 시계 read + PositionThesis 조립) · candidate 로드 ·
commit · envelope. top-level `risk_engine/thesis_sync.py` 는 thin CLI delegator.

LLM 위임 절대 금지 (G6). 멱등 / accepted+new_entry only / 다중 falsifier primary-only.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from domains._shared.positions_store.errors import PositionSchemaError
from domains._shared.positions_store.schema import PositionThesis, ThesisProvenance
# ── Boundary-injected deps (D-ARCH-4 / ADR-0005, invariant-D) ───────────────────
# application/ 은 _boundary 를 import 하지 않는다. 플랫 shim (risk_engine/thesis_sync.py)
# 이 composition root 로서 import 시 configure(_boundary) 로 아래 이름을 주입한다.
DEFAULT_ENV = base_report_envelope = commit_thesis = emit_summary_line = None
load_env_file = normalize_to_trading_day = now_iso_kst = positions_store = None
secret_safe_log = write_output_safely = None
_trail_dir = None


def configure(boundary: Any) -> None:
    """Composition-root wiring — 플랫 shim 이 _boundary 를 주입 (invariant-D 준수)."""
    g = globals()
    for _n in (
        "DEFAULT_ENV", "base_report_envelope", "commit_thesis", "emit_summary_line",
        "load_env_file", "normalize_to_trading_day", "now_iso_kst", "positions_store",
        "secret_safe_log", "write_output_safely",
    ):
        g[_n] = getattr(boundary, _n)
    g["_trail_dir"] = boundary.resolve_trail_dir


from domains.risk_engine.domain.thesis_projection import (
    collect_citations,
    project_edge_source,
    project_falsifier,
    project_spec,
)

SCHEMA_VERSION = "investment-stage5a-thesis-sync-v1"
STAGE_NAME = "stage5a-thesis-sync"
STAGE4_FILENAME = "04-thesis-candidates.json"
OUTPUT_FILENAME = "05a-thesis-sync.json"


# ============================================================
# Input
# ============================================================

def load_candidates(trail_dir: Path) -> tuple[list[dict[str, Any]], list[str]]:
    """$TRAIL_TODAY/04-thesis-candidates.json 의 candidates[] 를 load.

    미존재 / parse 실패 → ([], [warning]) (G8 — abort 않음, Default No-Action).
    """
    warnings: list[str] = []
    p = trail_dir / STAGE4_FILENAME
    if not p.exists():
        warnings.append(
            f"Stage 4 산출물 없음: {p}. Stage 4 thesis-auditor 미실행 또는 trail 불일치 "
            "→ thesis.json 파생 0건 (Default No-Action)."
        )
        return [], warnings
    try:
        with p.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        warnings.append(f"Stage 4 JSON parse 실패: {p} — {exc} (G8)")
        return [], warnings
    return list(data.get("candidates") or []), warnings


# ============================================================
# Assembly (시계 read — 순수 projection 은 domain/thesis_projection)
# ============================================================

def project_thesis(
    candidate: dict[str, Any], *, index: int, date: str
) -> tuple[PositionThesis, list[str]]:
    """accepted new_entry 후보 → PositionThesis. raise(PositionSchemaError) 가능."""
    thesis = candidate.get("thesis") or {}
    falsifier_spec, warnings = project_falsifier(thesis.get("falsifier") or {})

    entry_catalyst = thesis.get("entry_catalyst") or {}
    if isinstance(entry_catalyst, dict):
        catalyst_str = entry_catalyst.get("catalyst_id") or entry_catalyst.get("catalyst_type") or ""
    else:
        catalyst_str = str(entry_catalyst)

    horizon = thesis.get("time_horizon_months")
    asymmetry = thesis.get("asymmetry_score") or {}

    position = PositionThesis(
        ticker=candidate["ticker"],
        name=candidate.get("name") or candidate["ticker"],
        falsifier=falsifier_spec,
        entry_date=date,
        time_horizon_months=(float(horizon) if horizon is not None else None),
        edge_source=project_edge_source(thesis.get("edge_source")),
        entry_price_krw=None,  # 사용자 실진입 시 채움 (monitor tolerate)
        status="open",
        entry_catalyst=catalyst_str,
        asymmetry_score=asymmetry,
        provenance=ThesisProvenance(
            committed_at=now_iso_kst(),
            committed_by="stage4-derive",
            source=f"{STAGE4_FILENAME}#candidates[{index}]",
            citations=collect_citations(asymmetry),
            rationale_ko="stage4 accepted new_entry 후보에서 결정론 파생",
        ),
    )
    return position, warnings


# ============================================================
# main
# ============================================================

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Stage 5a — Thesis Sync (thesis.json writer)")
    parser.add_argument("--date", help="YYYY-MM-DD (KST). 기본: 오늘")
    parser.add_argument("--env", default=str(DEFAULT_ENV))
    parser.add_argument(
        "--trail-dir",
        default=None,
        help="trail 디렉토리 (기본: 오늘 KST 거래일 operations/{date})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="candidate scan 없이 빈 envelope 만 작성 (smoke test 용)",
    )
    args = parser.parse_args(argv)

    env = load_env_file(args.env)
    date = normalize_to_trading_day(args.date)
    trail_dir = Path(args.trail_dir) if args.trail_dir else _trail_dir(date)
    store = positions_store()

    all_warnings: list[str] = []
    written: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    if args.dry_run:
        all_warnings.append("--dry-run: candidate scan skipped")
        candidates: list[dict[str, Any]] = []
    else:
        candidates, load_warnings = load_candidates(trail_dir)
        all_warnings.extend(load_warnings)

    for i, cand in enumerate(candidates):
        ticker = cand.get("ticker") or "?"
        verdict = cand.get("verdict")
        kind = cand.get("thesis_kind")
        if verdict != "accepted":
            skipped.append({"ticker": ticker, "reason": f"verdict={verdict!r} != accepted"})
            continue
        if kind != "new_entry":
            # amendment / 기타 → 절대 auto-write 안 함 (user-gated).
            skipped.append({"ticker": ticker, "reason": f"thesis_kind={kind!r} != new_entry (user-gated)"})
            continue
        # 멱등 가드: thesis.json 이 이미 있으면 clobber 금지 (재진입/amendment 는 manual).
        if store.thesis_path(ticker).exists():
            skipped.append({"ticker": ticker, "reason": "기존 thesis.json 존재 — clobber 금지 (user-gated)"})
            continue
        try:
            position, proj_warnings = project_thesis(cand, index=i, date=date)
            for w in proj_warnings:
                all_warnings.append(secret_safe_log(f"[{ticker}] {w}", env))
            path = commit_thesis(position)
        except (PositionSchemaError, KeyError, TypeError, ValueError) as exc:
            all_warnings.append(
                secret_safe_log(f"[{ticker}] projection 실패 — skip: {type(exc).__name__}: {exc}", env)
            )
            skipped.append({"ticker": ticker, "reason": f"projection error: {type(exc).__name__}"})
            continue
        written.append(
            {
                "ticker": ticker,
                "thesis_path": str(path),
                "falsifier_category": position.falsifier.category,
            }
        )

    stats = {
        "candidates_scanned": len(candidates),
        "written": len(written),
        "skipped": len(skipped),
    }

    envelope = base_report_envelope(
        schema=SCHEMA_VERSION,
        date=date,
        config_path=str(trail_dir / STAGE4_FILENAME),
        config_version=1,
    )
    envelope.update(
        {
            "stats": stats,
            "written": written,
            "skipped": skipped,
            "warnings": [secret_safe_log(w, env) for w in all_warnings],
        }
    )

    out_path = trail_dir / OUTPUT_FILENAME
    final = write_output_safely(out_path, envelope)
    emit_summary_line(
        STAGE_NAME,
        {
            "date": date,
            "scanned": stats["candidates_scanned"],
            "written": stats["written"],
            "skipped": stats["skipped"],
            "warnings": len(all_warnings),
        },
        final,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
