"""Yield-curve Signal — US10Y - US2Y spread (FRED)."""
from __future__ import annotations

from typing import Any, Mapping

from domains.macro import _boundary
from domains.macro.domain.regime import IndicatorResult
from domains.macro.signals.base import Signal, empty_indicator
from domains.macro.signals.registry import register_signal


@register_signal("yield_curve")
class YieldCurveSignal(Signal):
    def fetch(self, env: Mapping[str, str], date: str) -> tuple[IndicatorResult, list[str]]:
        warnings: list[str] = []
        api_key = env.get("FRED_API_KEY", "")
        if not api_key:
            warnings.append("FRED_API_KEY missing → yield_curve indicator skipped")
            return empty_indicator("FRED_API_KEY missing"), warnings
        try:
            v10, d10 = _boundary.fred_latest(api_key, "DGS10", date)
            v2, d2 = _boundary.fred_latest(api_key, "DGS2", date)
        except _boundary.FetchError as exc:
            warnings.append(f"yield_curve fetch error: {exc}")
            return empty_indicator(str(exc)), warnings
        spread = round(v10 - v2, 4)
        label = (
            "inverted" if spread < 0
            else "flat" if spread < 0.5
            else "steepening" if spread < 1.5
            else "steep"
        )
        return (
            IndicatorResult(
                indicator="US10Y - US2Y",
                value=spread,
                value_label=label,
                source_citation=_boundary.format_citation(
                    "FRED",
                    f"{d10}/{d2}",
                    {"DGS10": v10, "DGS2": v2, "spread": spread},
                ),
            ),
            warnings,
        )

    def vote(
        self, result: IndicatorResult, thresholds: Mapping[str, Any]
    ) -> tuple[str, str] | None:
        if result.value is None:
            return None
        th = thresholds.get("yield_curve", {})
        v = result.value
        if v <= th.get("crisis_signal", -1.0):
            return "crisis", f"yield_curve={v:.2f} ≤ crisis_signal"
        if v <= th.get("late_cycle_signal", 0.0):
            return "late_cycle", f"yield_curve={v:.2f} ≤ late_cycle_signal (inverted)"
        return "mid_cycle", f"yield_curve={v:.2f} > 0 (non-inverted)"
