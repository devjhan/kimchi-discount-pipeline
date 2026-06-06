"""Breadth Signal — % above 200dma (S&P 500), loaded from breadth.yaml.

Stage 0a (``breadth_fetch.py``) 가 SPX fan-out 으로 breadth.yaml 을 prefetch 한다.
본 Signal 의 ``fetch`` 는 그 결과를 *로드만* 한다 — 무거운 500-ticker fan-out 은
Signal.fetch 로 끌어오지 않는다 (Stage 0a prefetch 캐시 유지, F-9 설계 경계).
"""
from __future__ import annotations

from typing import Any, Mapping

from domains.macro import _boundary
from domains.macro.domain.regime import IndicatorResult
from domains.macro.signals.base import Signal, empty_indicator
from domains.macro.signals.registry import register_signal


@register_signal("breadth")
class BreadthSignal(Signal):
    def fetch(self, env: Mapping[str, str], date: str) -> tuple[IndicatorResult, list[str]]:
        warnings: list[str] = []
        try:
            signal = _boundary.load_breadth_signal()
        except FileNotFoundError as exc:
            warnings.append(f"breadth signal not found: {exc}")
            return empty_indicator(str(exc)), warnings
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"breadth signal load fail: {type(exc).__name__}: {exc}")
            return empty_indicator(str(exc)), warnings

        pct: Any = signal.get("spx_above_200dma_pct")
        if pct is None:
            skip = signal.get("skip_reason") or "breadth.yaml.spx_above_200dma_pct=null"
            warnings.append(f"breadth signal value=null: {skip}")
            return empty_indicator(skip), warnings

        try:
            pct = float(pct)
        except (TypeError, ValueError):
            warnings.append(f"breadth signal value not numeric: {pct!r}")
            return empty_indicator("non-numeric breadth value"), warnings

        label = (
            "weak" if pct <= 0.2
            else "soft" if pct <= 0.4
            else "neutral" if pct < 0.6
            else "broad"
        )
        observed_at = signal.get("observed_at") or "unknown"
        source = signal.get("source") or _boundary.format_citation(
            "breadth_signal", observed_at, pct
        )
        return (
            IndicatorResult(
                indicator="% above 200dma (S&P 500)",
                value=round(pct, 4),
                value_label=label,
                source_citation=source,
            ),
            warnings,
        )

    def vote(
        self, result: IndicatorResult, thresholds: Mapping[str, Any]
    ) -> tuple[str, str] | None:
        if result.value is None:
            return None
        th = thresholds.get("breadth", {})
        v = result.value
        if v <= th.get("crisis_max", 0.2):
            return "crisis", f"breadth={v:.2f} ≤ crisis_max"
        if v <= th.get("late_cycle_max", 0.4):
            return "late_cycle", f"breadth={v:.2f} ≤ late_cycle_max"
        if v >= th.get("healthy_min", 0.6):
            return "mid_cycle", f"breadth={v:.2f} ≥ healthy_min"
        return None
