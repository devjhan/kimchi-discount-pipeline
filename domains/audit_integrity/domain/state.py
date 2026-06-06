"""Shadow portfolio 상태 값 객체 + serde (on-disk JSON ↔ dataclass).

on-disk schema 는 ``init_shadow_state.py --init`` 템플릿과 호환:
tier dict = {name, initial_capital_krw, current_nav_krw, cumulative_return_pct,
current_holdings, open_trades, closed_trades, last_rebalance_date} +
엔진 관리 필드 (cash_krw, quarterly_history). holding dict 에 entry_date 추가
(30일 보유 규칙용 — init 는 빈 holdings 라 호환).

paper trade only (G9): qty/price 는 가상. 자본 이동 / broker 호출 없음.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

TIER_KEYS = (
    "tier_0_passive_index",
    "tier_1_mechanical",
    "tier_2_llm_filtered",
    "tier_3_random",
)


@dataclass(frozen=True)
class Holding:
    ticker: str
    qty: float
    avg_cost_krw: float
    weight: float
    entry_date: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "ticker": self.ticker,
            "qty": round(self.qty, 8),
            "avg_cost_krw": round(self.avg_cost_krw, 4),
            "weight": round(self.weight, 6),
            "entry_date": self.entry_date,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Holding":
        return cls(
            ticker=str(d["ticker"]),
            qty=float(d.get("qty", 0.0)),
            avg_cost_krw=float(d.get("avg_cost_krw", 0.0)),
            weight=float(d.get("weight", 0.0)),
            entry_date=str(d.get("entry_date", "")),
        )


@dataclass(frozen=True)
class ClosedTrade:
    """trade-log-{tier}.csv 한 줄. ``tier`` 는 CSV 라우팅 키 (CSV 본문엔 미포함)."""

    tier: str
    trade_id: str
    ticker: str
    entry_date: str
    entry_price_krw: float
    exit_date: str
    exit_price_krw: float
    return_pct: float
    reason: str  # falsifier_triggered | 30_day_holding_max | rebalance | catalyst_inactive


@dataclass
class TierState:
    name: str
    initial_capital_krw: float
    cash_krw: float
    current_nav_krw: float
    cumulative_return_pct: float
    holdings: list[Holding]
    closed_trades: int
    last_rebalance_date: str | None
    quarterly_history: list[dict[str, Any]] = field(default_factory=list)

    @property
    def open_trades(self) -> int:
        return len(self.holdings)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "initial_capital_krw": self.initial_capital_krw,
            "cash_krw": round(self.cash_krw, 4),
            "current_nav_krw": round(self.current_nav_krw, 4),
            "cumulative_return_pct": round(self.cumulative_return_pct, 6),
            "current_holdings": [h.to_dict() for h in self.holdings],
            "open_trades": self.open_trades,
            "closed_trades": self.closed_trades,
            "last_rebalance_date": self.last_rebalance_date,
            "quarterly_history": list(self.quarterly_history),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "TierState":
        holdings = [Holding.from_dict(h) for h in d.get("current_holdings") or []]
        initial = float(d.get("initial_capital_krw", 100_000_000))
        # cash_krw 미존재 (init 템플릿) → holdings 없으면 initial, 있으면 nav - 보유원가 근사.
        if "cash_krw" in d:
            cash = float(d["cash_krw"])
        elif not holdings:
            cash = initial
        else:
            invested = sum(h.qty * h.avg_cost_krw for h in holdings)
            cash = float(d.get("current_nav_krw", initial)) - invested
        return cls(
            name=str(d.get("name", "")),
            initial_capital_krw=initial,
            cash_krw=cash,
            current_nav_krw=float(d.get("current_nav_krw", initial)),
            cumulative_return_pct=float(d.get("cumulative_return_pct", 0.0)),
            holdings=holdings,
            closed_trades=int(d.get("closed_trades", 0)),
            last_rebalance_date=d.get("last_rebalance_date"),
            quarterly_history=list(d.get("quarterly_history") or []),
        )


@dataclass
class ShadowPortfolioState:
    schema: str
    init_date: str
    tiers: dict[str, TierState]
    daily_snapshots: dict[str, Any]
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ShadowPortfolioState":
        tiers = {k: TierState.from_dict(v) for k, v in (d.get("tiers") or {}).items()}
        known = {"schema", "init_date", "tiers", "daily_snapshots"}
        extra = {k: v for k, v in d.items() if k not in known}
        return cls(
            schema=str(d.get("schema", "investment-shadow-portfolio-state-v1")),
            init_date=str(d.get("init_date", "")),
            tiers=tiers,
            daily_snapshots=dict(d.get("daily_snapshots") or {}),
            extra=extra,
        )

    def to_dict(self) -> dict[str, Any]:
        out = dict(self.extra)
        out.update(
            {
                "schema": self.schema,
                "init_date": self.init_date,
                "tiers": {k: t.to_dict() for k, t in self.tiers.items()},
                "daily_snapshots": self.daily_snapshots,
            }
        )
        return out
