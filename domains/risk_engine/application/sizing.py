"""Stage 5 sizing — orchestration + IO (입력 로드 / envelope / write).

F-8: 순수 규칙 (`domain/sizing.py`) 위의 application layer. 입력 (thesis-candidates /
macro-regime / portfolio context) 로드는 `_boundary` 경유, 사이즈 산수는 domain 위임.
top-level `risk_engine/sizing.py` 는 본 모듈 main() 을 호출하는 thin CLI.
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

from domains.risk_engine._boundary import (
    DEFAULT_ENV,
    DEFAULT_THRESHOLDS,
    base_report_envelope,
    emit_summary_line,
    load_derived_state,
    load_env_file,
    load_user_portfolio,
    load_yaml_config,
    normalize_to_trading_day,
    resolve_trail_dir as _trail_dir,
    secret_safe_log,
    write_output_safely,
)
from domains.risk_engine.domain.sizing import (
    SizeRecommendation,
    apply_portfolio_kelly_cap,
    size_one,
)

SCHEMA_VERSION = "investment-stage5-sizing-v1"
STAGE_NAME = "stage5-sizing"


# ============================================================
# Inputs
# ============================================================


def _load_thesis_candidates(date: str) -> tuple[list[dict[str, Any]], list[str]]:
    p = _trail_dir(date) / "04-thesis-candidates.json"
    if not p.exists():
        return [], [f"thesis-candidates 파일 미존재: {p}"]
    with p.open("r", encoding="utf-8") as f:
        import json

        data = json.load(f)
    return list(data.get("candidates") or []), []


def _load_macro_regime(date: str) -> tuple[dict[str, Any], list[str]]:
    p = _trail_dir(date) / "00-macro-regime.json"
    if not p.exists():
        return {}, [
            f"macro-regime 파일 미존재: {p} — cash_band 'unknown' fallback 적용"
        ]
    with p.open("r", encoding="utf-8") as f:
        import json

        return json.load(f), []


def _portfolio_context_from_yaml(*, date: str | None = None) -> tuple[dict[str, Any] | None, list[str]]:
    """
    사용자 portfolio.yaml + portfolio_state_derive (자동) 합성.

    우선순위:
        1. portfolio.yaml override (사용자 명시값, drawdown/cash 각각)
        2. _derived-{date}.json (자동 derive — positions_sync 후 portfolio_state_derive 산출)
        3. 0 fallback (drawdown), None (cash — band 검사 skip)

    total_capital_krw 는 사용자 manual 입력만 (자동 derive 안 함). 미입력 시 G12 boundary.

    Returns:
        ({total_krw, current_drawdown_pct, current_cash_pct}, warnings)
        또는 (None, warnings).
    """
    warnings: list[str] = []
    pf = load_user_portfolio()
    if not pf:
        warnings.append(
            "portfolio.yaml 미존재 → 사이즈 출력 보류 (G12). "
            "portfolio.yaml.example 을 cp 한 뒤 total_capital_krw 입력 필요."
        )
        return None, warnings
    raw_total = pf.get("total_capital_krw")
    if raw_total is None:
        warnings.append(
            "portfolio.yaml.total_capital_krw=null → 사이즈 출력 보류 (G12)."
        )
        return None, warnings
    try:
        total_krw = float(raw_total)
    except (TypeError, ValueError):
        warnings.append(f"portfolio.yaml.total_capital_krw invalid (got {raw_total!r})")
        return None, warnings

    # drawdown / cash 자동 derive fallback (read 를 _boundary 경유 → 순환 의존 제거)
    derived: dict[str, Any] | None = None
    if date:
        try:
            derived = load_derived_state(date)
        except Exception as exc:  # noqa: BLE001 — graceful fallback
            warnings.append(f"derived state load skip: {type(exc).__name__}: {exc}")
            derived = None

    drawdown_raw = pf.get("current_drawdown_pct")
    drawdown = 0.0
    if drawdown_raw is not None:
        try:
            drawdown = float(drawdown_raw)
        except (TypeError, ValueError):
            warnings.append(
                f"portfolio.yaml.current_drawdown_pct invalid (got {drawdown_raw!r}); 0 fallback"
            )
    elif derived and derived.get("current_drawdown_pct") is not None:
        try:
            drawdown = float(derived["current_drawdown_pct"])
            warnings.append(
                f"drawdown derived from positions_sync — {drawdown:.4f} "
                f"(source: _derived-{date}.json)"
            )
        except (TypeError, ValueError):
            warnings.append(
                f"derived current_drawdown_pct invalid; 0 fallback"
            )

    cash_raw = pf.get("current_cash_pct")
    current_cash_pct = None
    if cash_raw is not None:
        try:
            current_cash_pct = float(cash_raw)
        except (TypeError, ValueError):
            warnings.append(
                f"portfolio.yaml.current_cash_pct invalid (got {cash_raw!r}); current cash 미반영"
            )
    elif derived and derived.get("current_cash_pct") is not None:
        try:
            current_cash_pct = float(derived["current_cash_pct"])
            warnings.append(
                f"cash% derived from positions_sync — {current_cash_pct:.4f} "
                f"(source: _derived-{date}.json)"
            )
        except (TypeError, ValueError):
            warnings.append(
                f"derived current_cash_pct invalid; current cash 미반영"
            )

    return (
        {
            "total_krw": total_krw,
            "current_drawdown_pct": drawdown,
            "current_cash_pct": current_cash_pct,
        },
        warnings,
    )


# ============================================================
# CLI orchestration
# ============================================================


def main() -> int:
    parser = argparse.ArgumentParser(description="Stage 5 — Sizing Recommendation")
    parser.add_argument("--date", help="YYYY-MM-DD (KST). 기본: 오늘")
    parser.add_argument("--config", default=str(DEFAULT_THRESHOLDS))
    parser.add_argument("--env", default=str(DEFAULT_ENV))
    parser.add_argument("--trail-dir", default=None, help="output trail dir (default: $TRAIL_TODAY env, else operations/{KST 거래일})")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="입력 thesis-candidates 없어도 G12 boundary check만 수행하고 종료",
    )
    args = parser.parse_args()

    config = load_yaml_config(args.config)
    env = load_env_file(args.env)
    date = normalize_to_trading_day(args.date)
    all_warnings: list[str] = []

    candidates, cand_warns = _load_thesis_candidates(date)
    for w in cand_warns:
        all_warnings.append(secret_safe_log(w, env))

    macro, macro_warns = _load_macro_regime(date)
    for w in macro_warns:
        all_warnings.append(secret_safe_log(w, env))
    cash_band = macro.get("cash_band") or [0.30, 0.70]
    regime = (macro.get("regime_decision") or {}).get("regime", "unknown")

    portfolio_ctx, port_warns = _portfolio_context_from_yaml(date=date)
    for w in port_warns:
        all_warnings.append(secret_safe_log(w, env))

    if portfolio_ctx is None:
        # G12 — 사이즈 출력 보류
        payload = base_report_envelope(
            schema=SCHEMA_VERSION,
            date=date,
            config_path=args.config,
            config_version=config.get("version", "unknown"),
        )
        payload.update(
            {
                "portfolio_context": None,
                "regime": regime,
                "cash_band": cash_band,
                "recommendations": [],
                "warnings": all_warnings,
                "blocked_reason": (
                    "USER_PORTFOLIO_TOTAL_KRW 미입력 — Stage 5 사이즈 출력 보류 (G12). "
                    ".env에 portfolio context 입력 후 재실행."
                ),
            }
        )
        out_path = (Path(args.trail_dir) if args.trail_dir else _trail_dir(date)) / "05-sizing-recommendation.json"
        final = write_output_safely(out_path, payload)
        emit_summary_line(
            STAGE_NAME,
            {"date": date, "blocked": "G12_no_user_portfolio", "warnings": len(all_warnings)},
            final,
        )
        return 0

    # drawdown brake
    sizing_cfg = config.get("sizing", {})
    brake_threshold = float(sizing_cfg.get("drawdown_brake", {}).get("threshold_pct", 0.15))
    drawdown_brake_active = portfolio_ctx["current_drawdown_pct"] >= brake_threshold

    recs: list[SizeRecommendation] = []
    for c in candidates:
        recs.append(
            size_one(c, config, portfolio_ctx["total_krw"], drawdown_brake_active)
        )

    # portfolio Kelly cap
    portfolio_notes = apply_portfolio_kelly_cap(recs, config)

    # cash band check
    cash_pct = portfolio_ctx.get("current_cash_pct")
    cash_band_violation = (
        cash_pct is not None and cash_pct < cash_band[0]
    )
    if cash_band_violation:
        for r in recs:
            if r.verdict in ("size_recommended", "size_recommended_half_cap"):
                r.verdict = "blocked_cash_band"
                r.guards_applied.append(
                    f"current_cash_pct={cash_pct:.2f} < cash_band[0]={cash_band[0]:.2f} (G18)"
                )
                r.size_pct_of_portfolio = None
                r.size_krw = None

    by_verdict: dict[str, int] = {}
    for r in recs:
        by_verdict[r.verdict] = by_verdict.get(r.verdict, 0) + 1

    payload = base_report_envelope(
        schema=SCHEMA_VERSION,
        date=date,
        config_path=args.config,
        config_version=config.get("version", "unknown"),
    )
    payload.update(
        {
            "portfolio_context": {
                **portfolio_ctx,
                "regime": regime,
                "cash_band": cash_band,
                "drawdown_brake_active": drawdown_brake_active,
                "drawdown_brake_threshold": brake_threshold,
                "cash_band_violation": cash_band_violation,
            },
            "stats": {
                "total": len(recs),
                "by_verdict": by_verdict,
                "portfolio_kelly_notes": portfolio_notes,
            },
            "recommendations": [asdict(r) for r in recs],
            "warnings": all_warnings,
        }
    )
    out_path = (Path(args.trail_dir) if args.trail_dir else _trail_dir(date)) / "05-sizing-recommendation.json"
    final = write_output_safely(out_path, payload)
    summary = {
        "date": date,
        "regime": regime,
        "cash_band": f"{cash_band[0]:.2f}-{cash_band[1]:.2f}",
        "total": len(recs),
        **{f"v_{k}": v for k, v in by_verdict.items()},
        "warnings": len(all_warnings),
    }
    emit_summary_line(STAGE_NAME, summary, final)
    return 0


if __name__ == "__main__":
    sys.exit(main())
