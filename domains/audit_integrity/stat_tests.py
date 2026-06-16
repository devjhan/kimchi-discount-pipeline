"""
domains/audit_integrity/stat_tests.py — Welch t-test + bootstrap CI (stdlib only).

`investment-audit-outcome` skill 의 분기 비교에서 사용. tier_2 (LLM-Filtered)
와 tier_1 (Mechanical) 의 누적 분기 수익률 차이가 통계적으로 유의한지 측정해
self-disable trigger 의 noise 흔들림을 차단한다.

본 module 의 모든 통계 산출은 deterministic 하다 (LLM 위임 절대 금지, G6).
scipy / numpy 미사용 — Python 3.10+ stdlib (`statistics.NormalDist` + 직접
Welch 공식) 만으로 구현한다. 이유:
    1. pyproject.toml 의 의존성 최소화 원칙 준수 (scipy/numpy 추가 없이 stdlib 완결)
    2. 1 sample size 가 작아 (분기 단위 N=4~16) 직접 공식이 충분히 정밀
    3. caller (audit-outcome skill) 는 결과 dict 를 인용만 함

Hard guards:
    - G6:  통계 산출은 본 module 에서만 (LLM 위임 금지)
    - G7:  결과 인용 시 citation 형식 'STAT@{date}={...}' 사용 (caller 책임)
    - G19: sample size 미충족 시 wording 룰 자동 redact 는 caller (skill) 가 적용

Usage:
    from domains.audit_integrity.stat_tests import (
        welch_t_test, bootstrap_ci, evaluate_self_disable_trigger,
        quarterly_returns,
    )
"""

from __future__ import annotations

import json
import math
import random
import statistics
from pathlib import Path
from typing import Any

# ============================================================
# Welch t-test (stdlib only)
# ============================================================


def _mean_var(xs: list[float]) -> tuple[float, float]:
    """평균, 표본분산 (n-1 분모)."""
    n = len(xs)
    if n < 2:
        return (xs[0] if n == 1 else 0.0, 0.0)
    m = statistics.fmean(xs)
    var = statistics.variance(xs, xbar=m)
    return m, var


def welch_t_test(a: list[float], b: list[float]) -> dict[str, Any]:
    """
    a, b 두 표본의 평균 차이에 대한 Welch t-test (등분산 가정 안 함).

    Returns dict:
        t            : t statistic
        df           : Welch–Satterthwaite degree of freedom
        p_two_sided  : two-sided p-value (Normal CDF approximation when df >= 30,
                       otherwise None — small-sample exact 분포는 stdlib 부재)
        n_a, n_b     : sample sizes
        mean_a, mean_b
        var_a, var_b : 표본분산
        mean_diff    : mean(a) - mean(b)
        se_diff      : standard error of diff
        ci_95        : [low, high] using z-approx (df>=30 only; else None)
        method       : "welch_t_test"

    n_a < 2 또는 n_b < 2 → t/df/p 모두 None (insufficient sample).
    """
    n_a, n_b = len(a), len(b)
    if n_a < 2 or n_b < 2:
        return {
            "method": "welch_t_test",
            "t": None,
            "df": None,
            "p_two_sided": None,
            "n_a": n_a,
            "n_b": n_b,
            "mean_a": (statistics.fmean(a) if a else None),
            "mean_b": (statistics.fmean(b) if b else None),
            "var_a": None,
            "var_b": None,
            "mean_diff": None,
            "se_diff": None,
            "ci_95": None,
            "note": "insufficient sample (n_a < 2 또는 n_b < 2)",
        }
    mean_a, var_a = _mean_var(a)
    mean_b, var_b = _mean_var(b)
    se_a = var_a / n_a
    se_b = var_b / n_b
    se_diff_sq = se_a + se_b
    if se_diff_sq <= 0:
        return {
            "method": "welch_t_test",
            "t": None,
            "df": None,
            "p_two_sided": None,
            "n_a": n_a,
            "n_b": n_b,
            "mean_a": mean_a,
            "mean_b": mean_b,
            "var_a": var_a,
            "var_b": var_b,
            "mean_diff": mean_a - mean_b,
            "se_diff": 0.0,
            "ci_95": None,
            "note": "se_diff=0 — 두 표본 모두 분산 0 (degenerate)",
        }
    se_diff = math.sqrt(se_diff_sq)
    t = (mean_a - mean_b) / se_diff
    # Welch–Satterthwaite df
    num = se_diff_sq ** 2
    den = (se_a ** 2) / (n_a - 1) + (se_b ** 2) / (n_b - 1)
    df = num / den if den > 0 else float("inf")

    p_two_sided: float | None = None
    ci_95: list[float] | None = None
    note: str | None = None
    if df >= 30:
        # Normal approx for large df (well within 1% of t for df>=30)
        nd = statistics.NormalDist()
        p_two_sided = 2 * (1 - nd.cdf(abs(t)))
        z = nd.inv_cdf(0.975)
        ci_95 = [
            round((mean_a - mean_b) - z * se_diff, 6),
            round((mean_a - mean_b) + z * se_diff, 6),
        ]
    else:
        note = (
            f"df={df:.2f} < 30 — small-sample exact t-distribution 미산출 "
            "(stdlib 한계). 부호 / |t| 만 인용 권장."
        )

    return {
        "method": "welch_t_test",
        "t": round(t, 6),
        "df": round(df, 4),
        "p_two_sided": (round(p_two_sided, 6) if p_two_sided is not None else None),
        "n_a": n_a,
        "n_b": n_b,
        "mean_a": round(mean_a, 6),
        "mean_b": round(mean_b, 6),
        "var_a": round(var_a, 6),
        "var_b": round(var_b, 6),
        "mean_diff": round(mean_a - mean_b, 6),
        "se_diff": round(se_diff, 6),
        "ci_95": ci_95,
        "note": note,
    }


# ============================================================
# Bootstrap CI (deterministic seed, stdlib random)
# ============================================================


def bootstrap_ci(
    samples: list[float],
    iters: int = 10_000,
    seed: int = 42,
    alpha: float = 0.05,
) -> dict[str, Any]:
    """
    samples 의 평균에 대한 percentile bootstrap CI.

    samples 가 두 표본의 차이 (예: paired diff) 일 때만 의미 있음.
    독립 두 표본은 welch_t_test() 사용.

    Returns dict:
        method, n, iters, seed, alpha, mean, ci_low, ci_high.
    """
    n = len(samples)
    if n < 2:
        return {
            "method": "bootstrap_ci",
            "n": n,
            "iters": iters,
            "seed": seed,
            "alpha": alpha,
            "mean": (samples[0] if n == 1 else None),
            "ci_low": None,
            "ci_high": None,
            "note": "insufficient sample (n < 2)",
        }
    rng = random.Random(seed)
    means: list[float] = []
    for _ in range(iters):
        resample = [samples[rng.randrange(n)] for _ in range(n)]
        means.append(sum(resample) / n)
    means.sort()
    lo_idx = int(math.floor((alpha / 2) * iters))
    hi_idx = int(math.ceil((1 - alpha / 2) * iters)) - 1
    hi_idx = max(0, min(iters - 1, hi_idx))
    return {
        "method": "bootstrap_ci",
        "n": n,
        "iters": iters,
        "seed": seed,
        "alpha": alpha,
        "mean": round(sum(samples) / n, 6),
        "ci_low": round(means[lo_idx], 6),
        "ci_high": round(means[hi_idx], 6),
    }


# ============================================================
# Quarterly returns from shadow portfolio state
# ============================================================


def quarterly_returns(
    state_path: Path, tier: str, n_quarters: int | None = None
) -> list[float]:
    """
    shadow-portfolio/state.json 의 tiers[tier].quarterly_history list[float] 를 반환.

    quarterly_history schema (domains.audit_integrity.main 결정론 엔진이 갱신):
        [{"quarter": "2026-Q1", "return_pct": 0.034}, ...]
        또는 plain [0.034, -0.012, ...] (legacy)

    Args:
        state_path: $AUDIT_DIR/shadow-portfolio/state.json
        tier: 'tier_0_passive_index' | 'tier_1_mechanical' | 'tier_2_llm_filtered' | 'tier_3_random'
        n_quarters: 마지막 N개 분기만 반환 (None 이면 전체)

    Returns:
        list[float] — 분기 누적 수익률 (예: 0.034 = +3.4%). 미존재 시 [].
    """
    if not state_path.exists():
        return []
    with state_path.open("r", encoding="utf-8") as f:
        state = json.load(f)
    tiers = state.get("tiers") or {}
    t = tiers.get(tier)
    if not isinstance(t, dict):
        return []
    raw = t.get("quarterly_history") or []
    out: list[float] = []
    for item in raw:
        if isinstance(item, (int, float)):
            out.append(float(item))
        elif isinstance(item, dict) and "return_pct" in item:
            try:
                out.append(float(item["return_pct"]))
            except (TypeError, ValueError):
                continue
    if n_quarters is not None and n_quarters > 0:
        out = out[-n_quarters:]
    return out


# ============================================================
# Self-disable trigger evaluator
# ============================================================


def evaluate_self_disable_trigger(
    state: dict[str, Any],
    gates: dict[str, Any] | None = None,
    *,
    consecutive_required: int = 4,
    p_max: float = 0.10,
) -> dict[str, Any]:
    """
    tier_2 vs tier_1 분기 누적 비교 → self-disable trigger 발동 여부.

    조건 (강화 — 단순 부호 → 통계적 유의성 결합):
        1. 최근 `consecutive_required` 분기 모두 tier_2 - tier_1 < 0 (sign-only)
        2. AND Welch p_two_sided < p_max  (df>=30 시 산출되는 p-value)

    p_two_sided 가 None (df < 30) 일 때는 sign-only 충족 시 'trigger_armed_directional'
    상태로 반환 — 사용자 명시 결정 요구.

    Returns dict:
        consecutive_quarters: 최근 음수 분기 연속 수
        consec_passed_sign  : bool
        consec_passed_p     : bool | None
        trigger_armed       : bool
        rationale           : str
        welch               : welch_t_test 결과 (전체 quarterly_history 기준)
    """
    tiers = state.get("tiers") or {}
    t1 = (tiers.get("tier_1_mechanical") or {}).get("quarterly_history") or []
    t2 = (tiers.get("tier_2_llm_filtered") or {}).get("quarterly_history") or []

    def _flatten(raw: list[Any]) -> list[float]:
        out: list[float] = []
        for it in raw:
            if isinstance(it, (int, float)):
                out.append(float(it))
            elif isinstance(it, dict) and "return_pct" in it:
                try:
                    out.append(float(it["return_pct"]))
                except (TypeError, ValueError):
                    continue
        return out

    a = _flatten(t2)
    b = _flatten(t1)
    n = min(len(a), len(b))

    consec = 0
    if n >= 1:
        for i in range(1, n + 1):
            if a[-i] < b[-i]:
                consec += 1
            else:
                break

    welch = welch_t_test(a, b)
    consec_passed_sign = consec >= consecutive_required
    p = welch.get("p_two_sided")
    consec_passed_p: bool | None
    if p is None:
        consec_passed_p = None
    else:
        consec_passed_p = bool(p < p_max and (welch.get("mean_diff") or 0) < 0)

    trigger_armed = bool(consec_passed_sign and (consec_passed_p is True))

    if not consec_passed_sign:
        rationale = (
            f"최근 음수 분기 연속 {consec} < {consecutive_required} — sign-only 미충족"
        )
    elif consec_passed_p is None:
        rationale = (
            f"sign-only 충족 (연속 {consec}분기 < 0) — p-value 미산출 (df<30). "
            "사용자 명시 결정 필요."
        )
    elif consec_passed_p is False:
        rationale = (
            f"sign-only 충족 (연속 {consec}분기 < 0) but p={p:.4f} >= {p_max} — "
            "통계적 유의성 미달, trigger 보류"
        )
    else:
        rationale = (
            f"sign-only 충족 (연속 {consec}분기 < 0) AND p={p:.4f} < {p_max} → trigger 발동"
        )

    return {
        "consecutive_quarters": consec,
        "consecutive_required": consecutive_required,
        "consec_passed_sign": consec_passed_sign,
        "consec_passed_p": consec_passed_p,
        "p_max": p_max,
        "trigger_armed": trigger_armed,
        "rationale": rationale,
        "welch": welch,
    }


__all__ = [
    "welch_t_test",
    "bootstrap_ci",
    "quarterly_returns",
    "evaluate_self_disable_trigger",
]
