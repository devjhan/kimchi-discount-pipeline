"""run_daily_update — 4-tier shadow portfolio 일별 paper-trade 엔진 (I/O 無, 결정론).

구 ``investment-audit-shadow-portfolio`` 스킬 산문(SKILL.md:83-140)이 LLM 으로 매일
수행하던 엔진을 재현가능한 코드로 회수 (F-6). 가격은 ``price_for`` 콜백으로 주입 —
본 모듈은 외부 I/O 0. paper trade only (G9): 자본 이동 / broker 호출 없음.

결정론 semantics (greenfield spec — 기존 live state 없음):
- 공통 paper 기계: 각 tier 는 cash + Σ(qty·price) = NAV. 진입 시 alloc 만큼 cash→holding,
  청산 시 holding→cash + closed trade 기록. fractional share (lot 제약 없음).
- tier_0 passive_index: tier0_tickers 동일비중(기본 50/50). weight drift > rebalance_threshold
  시 전량 청산(reason=rebalance) 후 재진입. 첫날 미보유면 진입.
- tier_1 mechanical: top-K(기본 5) primary catalyst ticker 동일비중. 보유가 오늘 catalyst 에
  없고 age>max_hold_days(30) → 청산(reason=catalyst_inactive). 빈 slot 신규 진입.
- tier_2 llm_filtered: 05 size_recommended(+half_cap) ticker 를 size_pct_of_portfolio 비중
  진입. 05c falsifier signal=triggered → 청산(reason=falsifier_triggered).
- tier_3 random: universe∩quality pool 에서 date-hash seed 로 K 선택 동일비중. age>30 → 청산
  (reason=30_day_holding_max). 빈 slot 신규 진입.
- 가격 미가용 ticker: 신규 진입 보류 + warning(G8). 보유분 평가는 avg_cost fallback.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from domains.audit_integrity.domain.rules import (
    deterministic_random_k,
    holding_age_days,
    max_weight_drift,
    quarter_of,
    trade_return_pct,
)
from domains.audit_integrity.domain.state import (
    ClosedTrade,
    Holding,
    ShadowPortfolioState,
    TierState,
)

# price_for(ticker) -> (price_krw | None, citation | None)
PriceFn = Callable[[str], "tuple[float | None, str | None]"]


@dataclass(frozen=True)
class EngineConfig:
    top_k: int = 5
    max_hold_days: int = 30
    rebalance_threshold_pct: float = 0.05
    tier0_target_weight: float = 0.5


@dataclass(frozen=True)
class DailyInputs:
    date: str
    tier0_tickers: tuple[str, ...]
    tier1_candidates: tuple[str, ...]
    tier1_active_catalysts: frozenset[str]
    tier2_recs: tuple[tuple[str, float], ...]  # (ticker, size_pct_of_portfolio)
    tier2_falsifier_triggered: frozenset[str]
    tier3_pool: tuple[str, ...]


@dataclass
class UpdateResult:
    state: ShadowPortfolioState
    closed_trades: list[ClosedTrade]
    warnings: list[str]
    citations: list[str]


class _Ctx:
    """run 단위 가격 캐시 + G7 citation 수집 + warning."""

    def __init__(self, price_for: PriceFn) -> None:
        self._price_for = price_for
        self._cache: dict[str, float | None] = {}
        self.citations: dict[str, str] = {}
        self.warnings: list[str] = []

    def price(self, ticker: str) -> float | None:
        if ticker not in self._cache:
            p, cite = self._price_for(ticker)
            self._cache[ticker] = p
            if p is not None and cite:
                self.citations[ticker] = cite
        return self._cache[ticker]

    def value(self, h: Holding) -> float:
        p = self.price(h.ticker)
        return h.qty * (p if p is not None else h.avg_cost_krw)


def run_daily_update(
    state: ShadowPortfolioState,
    inputs: DailyInputs,
    config: EngineConfig,
    price_for: PriceFn,
) -> UpdateResult:
    ctx = _Ctx(price_for)
    closed: list[ClosedTrade] = []

    _update_tier0(state.tiers.get("tier_0_passive_index"), inputs, config, ctx, closed)
    _update_slot_tier(
        state.tiers.get("tier_1_mechanical"),
        targets=list(inputs.tier1_candidates),
        date=inputs.date,
        config=config,
        ctx=ctx,
        closed=closed,
        tier_key="tier_1_mechanical",
        active_catalysts=inputs.tier1_active_catalysts,
    )
    _update_tier2(state.tiers.get("tier_2_llm_filtered"), inputs, config, ctx, closed)
    _update_slot_tier(
        state.tiers.get("tier_3_random"),
        targets=deterministic_random_k(inputs.tier3_pool, config.top_k, inputs.date),
        date=inputs.date,
        config=config,
        ctx=ctx,
        closed=closed,
        tier_key="tier_3_random",
        active_catalysts=None,
    )

    _record_snapshot_and_quarter(state, inputs.date)

    return UpdateResult(
        state=state,
        closed_trades=closed,
        warnings=ctx.warnings,
        citations=sorted(set(ctx.citations.values())),
    )


# ----------------------------------------------------------------------
# shared paper-trade primitives
# ----------------------------------------------------------------------


def _nav(tier: TierState, ctx: _Ctx) -> float:
    return tier.cash_krw + sum(ctx.value(h) for h in tier.holdings)


def _close(
    tier: TierState,
    tier_key: str,
    h: Holding,
    exit_price: float,
    date: str,
    reason: str,
    closed: list[ClosedTrade],
) -> None:
    seq = tier.closed_trades + 1
    closed.append(
        ClosedTrade(
            tier=tier_key,
            trade_id=f"{h.ticker}-{date}-{seq}",
            ticker=h.ticker,
            entry_date=h.entry_date,
            entry_price_krw=round(h.avg_cost_krw, 4),
            exit_date=date,
            exit_price_krw=round(exit_price, 4),
            return_pct=trade_return_pct(h.avg_cost_krw, exit_price),
            reason=reason,
        )
    )
    tier.cash_krw += h.qty * exit_price
    tier.closed_trades = seq


def _open(tier: TierState, ticker: str, alloc: float, price: float, date: str) -> None:
    alloc = min(alloc, tier.cash_krw)
    if alloc <= 0 or price <= 0:
        return
    tier.cash_krw -= alloc
    tier.holdings.append(Holding(ticker, alloc / price, price, 0.0, date))


def _finalize(tier: TierState, ctx: _Ctx) -> None:
    """NAV/cumulative_return 확정 + holding weight 재계산."""
    nav = _nav(tier, ctx)
    tier.current_nav_krw = round(nav, 4)
    base = tier.initial_capital_krw or 1.0
    tier.cumulative_return_pct = round(nav / base - 1.0, 6)
    if nav > 0:
        tier.holdings = [
            Holding(h.ticker, h.qty, h.avg_cost_krw, round(ctx.value(h) / nav, 6), h.entry_date)
            for h in tier.holdings
        ]


# ----------------------------------------------------------------------
# per-tier processors
# ----------------------------------------------------------------------


def _update_tier0(
    tier: TierState | None, inputs: DailyInputs, config: EngineConfig, ctx: _Ctx, closed: list[ClosedTrade]
) -> None:
    if tier is None:
        return
    tickers = list(inputs.tier0_tickers)
    prices = {t: ctx.price(t) for t in tickers}
    if any(prices[t] is None for t in tickers):
        ctx.warnings.append(
            f"tier_0: 가격 미가용 {[t for t in tickers if prices[t] is None]} — rebalance/entry skip"
        )
        _finalize(tier, ctx)
        return

    nav = _nav(tier, ctx)
    held = {h.ticker: h for h in tier.holdings}
    need_rebalance = not tier.holdings
    if tier.holdings and nav > 0:
        weights = [(held[t].qty * prices[t]) / nav for t in tickers if t in held]
        if max_weight_drift(weights, config.tier0_target_weight) > config.rebalance_threshold_pct:
            need_rebalance = True

    if need_rebalance:
        for h in list(tier.holdings):
            _close(tier, "tier_0_passive_index", h, prices[h.ticker], inputs.date, "rebalance", closed)
        tier.holdings = []
        cash_for_entry = tier.cash_krw
        for t in tickers:
            _open(tier, t, cash_for_entry * config.tier0_target_weight, prices[t], inputs.date)
        tier.last_rebalance_date = inputs.date

    _finalize(tier, ctx)


def _update_slot_tier(
    tier: TierState | None,
    *,
    targets: list[str],
    date: str,
    config: EngineConfig,
    ctx: _Ctx,
    closed: list[ClosedTrade],
    tier_key: str,
    active_catalysts: frozenset[str] | None,
) -> None:
    """tier_1 / tier_3 공통 — K-slot 동일비중, rule 기반 청산 + 빈 slot 진입."""
    if tier is None:
        return
    survivors: list[Holding] = []
    for h in tier.holdings:
        age = holding_age_days(h.entry_date, date)
        if active_catalysts is not None:  # tier_1: catalyst 미갱신 + 30일 초과
            exit_now = (h.ticker not in active_catalysts) and age > config.max_hold_days
            reason = "catalyst_inactive"
        else:  # tier_3: 30일 보유 만료
            exit_now = age > config.max_hold_days
            reason = "30_day_holding_max"
        if exit_now:
            p = ctx.price(h.ticker)
            _close(tier, tier_key, h, p if p is not None else h.avg_cost_krw, date, reason, closed)
        else:
            survivors.append(h)
    tier.holdings = survivors

    nav = _nav(tier, ctx)
    held_tickers = {h.ticker for h in tier.holdings}
    for t in targets:
        if len(tier.holdings) >= config.top_k:
            break
        if t in held_tickers:
            continue
        p = ctx.price(t)
        if p is None:
            ctx.warnings.append(f"{tier_key}: {t} 가격 미가용 — 진입 보류 (G8)")
            continue
        _open(tier, t, nav / config.top_k, p, date)
        held_tickers.add(t)

    _finalize(tier, ctx)


def _update_tier2(
    tier: TierState | None, inputs: DailyInputs, config: EngineConfig, ctx: _Ctx, closed: list[ClosedTrade]
) -> None:
    if tier is None:
        return
    survivors: list[Holding] = []
    for h in tier.holdings:
        if h.ticker in inputs.tier2_falsifier_triggered:
            p = ctx.price(h.ticker)
            _close(
                tier, "tier_2_llm_filtered", h, p if p is not None else h.avg_cost_krw,
                inputs.date, "falsifier_triggered", closed,
            )
        else:
            survivors.append(h)
    tier.holdings = survivors

    nav = _nav(tier, ctx)
    held_tickers = {h.ticker for h in tier.holdings}
    for ticker, size_pct in inputs.tier2_recs:
        if ticker in held_tickers:
            continue
        p = ctx.price(ticker)
        if p is None:
            ctx.warnings.append(f"tier_2: {ticker} 가격 미가용 — 진입 보류 (G8)")
            continue
        _open(tier, ticker, nav * float(size_pct), p, inputs.date)
        held_tickers.add(ticker)

    _finalize(tier, ctx)


# ----------------------------------------------------------------------
# snapshot + quarter rollover
# ----------------------------------------------------------------------


def _record_snapshot_and_quarter(state: ShadowPortfolioState, date: str) -> None:
    snaps = state.daily_snapshots
    prev_dates = sorted(d for d in snaps if d < date)
    snaps[date] = {k: round(t.current_nav_krw, 4) for k, t in state.tiers.items()}

    if not prev_dates:
        return
    prev_date = prev_dates[-1]
    if quarter_of(prev_date) == quarter_of(date):
        return
    closed_q = quarter_of(prev_date)
    q_dates = [d for d in snaps if quarter_of(d) == closed_q]
    if not q_dates:
        return
    first_d, last_d = min(q_dates), max(q_dates)
    for k, tier in state.tiers.items():
        if any(h.get("quarter") == closed_q for h in tier.quarterly_history):
            continue
        nav_start = (snaps.get(first_d) or {}).get(k)
        nav_end = (snaps.get(last_d) or {}).get(k)
        if not nav_start or nav_end is None:
            continue
        tier.quarterly_history.append(
            {"quarter": closed_q, "return_pct": round(nav_end / nav_start - 1.0, 6)}
        )
