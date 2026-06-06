"""Portfolio derived-state 의 순수 도메인 — value object + drawdown / cash% 산식.

F-8: ``DerivedPortfolioState`` value object + drawdown / cash 비율 산식을 IO (summary
scan) 와 분리해 회수. 본 모듈은 **순수** — IO / `_boundary` 접근 0. summary 파일 scan /
citation 조립은 ``application/portfolio_state.py``.

Hard guards: G6 (drawdown / cash% 결정론 산식).
"""
from __future__ import annotations

from dataclasses import dataclass, field

SCHEMA_VERSION = "investment-portfolio-derived-v1"
DEFAULT_LOOKBACK_DAYS = 365


@dataclass
class DerivedState:
    schema: str = SCHEMA_VERSION
    date: str = ""
    peak_total_assets_krw: float | None = None
    peak_observed_at: str | None = None
    current_total_assets_krw: float | None = None
    current_cash_krw: float | None = None
    current_drawdown_pct: float | None = None
    current_cash_pct: float | None = None
    source_citations: list[str] = field(default_factory=list)
    skip_reason: str | None = None
    lookback_days: int = DEFAULT_LOOKBACK_DAYS
    summaries_scanned: int = 0
    warnings: list[str] = field(default_factory=list)


def compute_drawdown_pct(peak: float | None, current: float | None) -> float | None:
    """max(0, (peak - current) / peak). 정의 불가 시 None."""
    if peak is None or current is None or peak <= 0:
        return None
    return max(0.0, round((peak - current) / peak, 6))


def compute_cash_pct(cash: float | None, total: float | None) -> float | None:
    """current_cash / current_total_assets. 정의 불가 시 None."""
    if total is None or total <= 0 or cash is None:
        return None
    return round(cash / total, 6)
