"""Credit-spread Signal — BAML HY OAS (FRED)."""
from __future__ import annotations

from typing import Any, Mapping

from domains.macro import _boundary
from domains.macro.domain.regime import IndicatorResult
from domains.macro.signals.base import Signal, empty_indicator
from domains.macro.signals.registry import register_signal


@register_signal("credit_spread")
class CreditSpreadSignal(Signal):
    def fetch(self, env: Mapping[str, str], date: str) -> tuple[IndicatorResult, list[str]]:
        warnings: list[str] = []
        api_key = env.get("FRED_API_KEY", "")
        if not api_key:
            warnings.append("FRED_API_KEY missing → credit_spread indicator skipped")
            return empty_indicator("FRED_API_KEY missing"), warnings
        try:
            v, d = _boundary.fred_latest(api_key, "BAMLH0A0HYM2", date)
        except _boundary.FetchError as exc:
            warnings.append(f"credit_spread fetch error: {exc}")
            return empty_indicator(str(exc)), warnings
        label = "tight" if v < 4.0 else "moderate" if v < 5.0 else "stress" if v < 8.0 else "crisis"
        return (
            IndicatorResult(
                indicator="BAML HY OAS",
                value=round(v, 4),
                value_label=label,
                source_citation=_boundary.format_citation("FRED", d, {"BAMLH0A0HYM2": v}),
            ),
            warnings,
        )

    def vote(
        self, result: IndicatorResult, thresholds: Mapping[str, Any]
    ) -> tuple[str, str] | None:
        if result.value is None:
            return None
        th = thresholds.get("credit_spread", {})
        v = result.value
        if v >= th.get("crisis_min", 8.0):
            return "crisis", f"credit_spread={v:.2f} ≥ crisis_min"
        if v >= th.get("late_cycle_min", 5.0):
            return "late_cycle", f"credit_spread={v:.2f} ≥ late_cycle_min"
        if v <= th.get("mid_cycle_max", 4.0):
            return "mid_cycle", f"credit_spread={v:.2f} ≤ mid_cycle_max"
        return None
