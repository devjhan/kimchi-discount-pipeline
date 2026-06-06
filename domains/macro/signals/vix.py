"""VIX Signal — VIXCLS + 5y rolling percentile (FRED)."""
from __future__ import annotations

from typing import Any, Mapping

from domains.macro import _boundary
from domains.macro.domain.regime import IndicatorResult
from domains.macro.signals._stats import percentile as _percentile
from domains.macro.signals.base import Signal, empty_indicator
from domains.macro.signals.registry import register_signal


@register_signal("vix")
class VixSignal(Signal):
    def fetch(self, env: Mapping[str, str], date: str) -> tuple[IndicatorResult, list[str]]:
        warnings: list[str] = []
        api_key = env.get("FRED_API_KEY", "")
        if not api_key:
            warnings.append("FRED_API_KEY missing → vix indicator skipped")
            return empty_indicator("FRED_API_KEY missing"), warnings
        try:
            v, d = _boundary.fred_latest(api_key, "VIXCLS", date)
            history = _boundary.fred_history_values(api_key, "VIXCLS", date, years=5)
        except _boundary.FetchError as exc:
            warnings.append(f"vix fetch error: {exc}")
            return empty_indicator(str(exc)), warnings
        pct = _percentile(history, v)
        if pct is None:
            warnings.append("vix history empty → percentile=null")
            return empty_indicator("VIX 5y history empty"), warnings
        label = (
            "panic" if pct >= 0.85
            else "elevated" if pct >= 0.60
            else "normal" if pct >= 0.30
            else "complacent"
        )
        return (
            IndicatorResult(
                indicator="VIX percentile (5y rolling)",
                value=round(v, 4),
                value_label=label,
                source_citation=_boundary.format_citation(
                    "FRED", d, {"VIXCLS": v, "percentile_5y": pct, "n_history": len(history)}
                ),
                percentile=round(pct, 4),
            ),
            warnings,
        )

    def vote(
        self, result: IndicatorResult, thresholds: Mapping[str, Any]
    ) -> tuple[str, str] | None:
        if result.percentile is None:
            return None
        th = thresholds.get("vix", {})
        p = result.percentile
        if p >= th.get("panic_min", 0.85):
            return "crisis", f"vix_percentile={p:.2f} ≥ panic_min"
        if p <= th.get("complacent_max", 0.20):
            return (
                "late_cycle",
                f"vix_percentile={p:.2f} ≤ complacent_max (complacency = late-cycle warning)",
            )
        return None
