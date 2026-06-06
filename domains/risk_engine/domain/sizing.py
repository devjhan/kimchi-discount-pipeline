"""Stage 5 sizing 의 순수 도메인 규칙 — value object + Kelly/asymmetry 산수.

F-8: 절차적으로 sizing.py 에 박혀 있던 순수 규칙 (asymmetry parse / fractional
Kelly / per-position·drawdown guard) 을 IO·orchestration 과 분리해 도메인으로 회수.
본 모듈은 **순수** — 외부 IO / `_boundary` / 파일 / env 접근 0. 모든 입력은 인자로
주입되고 산출은 ``SizeRecommendation``.

Hard guards (1번 사상 생존): G5 asymmetry / G16 per-position cap + 합산 Kelly cap /
G17 drawdown brake — 전부 본 모듈의 결정론 산수 (LLM 위임 금지, G6).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SizeRecommendation:
    ticker: str
    name: str
    verdict: str
    # 'size_recommended' | 'size_recommended_half_cap' | 'rejected_low_asymmetry'
    # | 'rejected_no_user_context' | 'blocked_drawdown_brake'
    # | 'blocked_cash_band' | 'needs_user_decision'
    size_pct_of_portfolio: float | None = None
    size_krw: float | None = None
    size_inputs: dict[str, Any] = field(default_factory=dict)
    rationale: list[str] = field(default_factory=list)
    guards_applied: list[str] = field(default_factory=list)
    rejection_reason: str | None = None


# ============================================================
# Asymmetry parser
# ============================================================

PCT_RE = re.compile(r"^([+-]?\d+(?:\.\d+)?)\s*%$")


def parse_pct(value: Any) -> float | None:
    """
    '-30%' → 0.30 (절대값 fraction), '+120%' → 1.20.
    숫자 / 다른 형식은 None.
    """
    if value is None:
        return None
    s = str(value).strip()
    m = PCT_RE.match(s)
    if not m:
        return None
    try:
        v = float(m.group(1)) / 100.0
    except ValueError:
        return None
    return abs(v)


def extract_asymmetry_ratio(asym: dict[str, Any]) -> tuple[float | None, str | None]:
    """
    Stage 4의 asymmetry_score 본문 (downside_floor / upside_ceiling)에서 ratio 산출.
    return (ratio, error_msg). ratio = upside_pct / downside_pct.
    """
    df = (asym or {}).get("downside_floor") or {}
    uc = (asym or {}).get("upside_ceiling") or {}
    df_v = parse_pct(df.get("krw_per_share_or_pct"))
    uc_v = parse_pct(uc.get("krw_per_share_or_pct"))
    if df_v is None or uc_v is None:
        return None, (
            "asymmetry parse fail — downside_floor/upside_ceiling % 형식이 아님 "
            "(KRW 절대값은 1차 미지원, 후속 helper에서 가격 fetch 필요)"
        )
    if df_v == 0:
        return None, "downside_floor=0 — Kelly 정의 안 됨"
    return round(uc_v / df_v, 4), None


# ============================================================
# Kelly compute (assuming p=0.5 — base case)
# ============================================================
# 본 시스템은 p (win prob) 추정에 hubris를 두지 않는다. 보수적으로 p=0.5
# 기준 + fractional kelly (1/4 ~ 1/2). 사용자가 별도 confidence 입력하면
# 후속 버전에서 반영. (1차 버전 명시 단순화.)


def compute_fractional_kelly(asymmetry_ratio: float, fraction: float) -> float:
    """
    f* = p - q/b   (p=0.5, q=0.5, b=asymmetry_ratio)
    fractional_kelly = f* × fraction (quarter-Kelly default)
    f* < 0 (b<1 — no edge) 인 경우 0.
    """
    p, q = 0.5, 0.5
    raw = p - q / asymmetry_ratio
    if raw < 0:
        return 0.0
    return round(raw * fraction, 6)


# ============================================================
# Sizing logic (순수 — cfg + 입력 → SizeRecommendation)
# ============================================================


def size_one(
    candidate: dict[str, Any],
    cfg: dict[str, Any],
    portfolio_total_krw: float,
    drawdown_brake_active: bool,
) -> SizeRecommendation:
    ticker = candidate.get("ticker", "?")
    name = candidate.get("name", ticker)
    verdict_in = candidate.get("verdict")
    if verdict_in != "accepted":
        return SizeRecommendation(
            ticker=ticker,
            name=name,
            verdict="rejected_no_user_context"
            if verdict_in is None
            else "needs_user_decision",
            rejection_reason=f"thesis verdict={verdict_in!r} != 'accepted'",
        )

    thesis = candidate.get("thesis") or {}
    asym = thesis.get("asymmetry_score") or {}
    ratio, err = extract_asymmetry_ratio(asym)
    sizing_cfg = cfg.get("sizing", {})
    asym_cfg = cfg.get("thesis", {}).get("asymmetry", {})
    min_ratio = float(asym_cfg.get("min_ratio", 2.0))
    half_below = float(asym_cfg.get("half_size_below_ratio", 3.0))
    reject_below_min = bool(asym_cfg.get("reject_below_min", False))
    fraction = float(sizing_cfg.get("kelly", {}).get("fraction", 0.25))
    max_pct = float(sizing_cfg.get("per_position", {}).get("max_pct", 0.25))
    min_pct = float(sizing_cfg.get("per_position", {}).get("min_pct", 0.02))

    if ratio is None:
        return SizeRecommendation(
            ticker=ticker,
            name=name,
            verdict="needs_user_decision",
            rejection_reason=err,
        )
    rec = SizeRecommendation(
        ticker=ticker,
        name=name,
        verdict="size_recommended",
        size_inputs={
            "asymmetry_ratio": ratio,
            "min_ratio": min_ratio,
            "half_size_below_ratio": half_below,
            "kelly_fraction": fraction,
            "position_cap": max_pct,
        },
    )

    # G5 asymmetry guard
    if ratio < min_ratio:
        if reject_below_min:
            rec.verdict = "rejected_low_asymmetry"
            rec.rejection_reason = (
                f"asymmetry_ratio={ratio:.2f} < min_ratio={min_ratio} (G5 reject)"
            )
            return rec
        rec.guards_applied.append(
            f"asymmetry_ratio={ratio:.2f} < min_ratio={min_ratio} → "
            f"reject_below_min=false → size 절반 cap 적용"
        )
        rec.verdict = "size_recommended_half_cap"

    raw_kelly = compute_fractional_kelly(ratio, 1.0)  # un-fractioned
    fractional = compute_fractional_kelly(ratio, fraction)
    rec.size_inputs["raw_kelly"] = raw_kelly
    rec.size_inputs["fractional_kelly"] = fractional
    proposed = fractional

    # half_size_below_ratio 분기
    if ratio < half_below:
        proposed = round(proposed / 2, 6)
        rec.guards_applied.append(
            f"asymmetry_ratio={ratio:.2f} < half_size_below_ratio={half_below} → 사이즈 절반"
        )

    # per_position cap
    if proposed > max_pct:
        rec.guards_applied.append(
            f"per_position.max_pct={max_pct} 적용 (proposed {proposed:.4f})"
        )
        proposed = max_pct

    # min_pct floor
    if proposed < min_pct:
        rec.verdict = "rejected_low_asymmetry"
        rec.rejection_reason = (
            f"size {proposed:.4f} < min_pct={min_pct} (G16 의 의미 있는 진입 규모 미달)"
        )
        return rec

    # G17 drawdown brake
    if drawdown_brake_active:
        proposed = round(proposed / 2, 6)
        rec.guards_applied.append("G17 drawdown brake → 사이즈 절반")

    rec.size_pct_of_portfolio = round(proposed, 6)
    rec.size_krw = round(proposed * portfolio_total_krw, 0)
    rec.rationale = [
        f"asymmetry_ratio={ratio:.2f} (upside / downside)",
        f"raw_kelly={raw_kelly:.4f} (p=0.5 base)",
        f"fractional_kelly={fractional:.4f} (×{fraction} fraction)",
    ] + rec.guards_applied
    return rec


def apply_portfolio_kelly_cap(
    recs: list[SizeRecommendation], cfg: dict[str, Any]
) -> list[str]:
    """portfolio 합산 Kelly가 cap 초과 시 비율 축소. notes return."""
    cap = float(cfg.get("sizing", {}).get("kelly", {}).get("portfolio_kelly_cap", 0.5))
    sized = [r for r in recs if r.size_pct_of_portfolio is not None]
    total = sum(r.size_pct_of_portfolio or 0 for r in sized)
    notes: list[str] = []
    if total <= cap or total == 0:
        return notes
    factor = cap / total
    for r in sized:
        old = r.size_pct_of_portfolio or 0
        new = round(old * factor, 6)
        r.size_pct_of_portfolio = new
        if r.size_krw is not None:
            r.size_krw = round(r.size_krw * factor, 0)
        r.guards_applied.append(
            f"portfolio_kelly_cap={cap} 적용 (sum {total:.4f} → ×{factor:.4f})"
        )
    notes.append(
        f"portfolio Kelly sum {total:.4f} > cap {cap} → 비율 축소 ({factor:.4f}x)"
    )
    return notes
