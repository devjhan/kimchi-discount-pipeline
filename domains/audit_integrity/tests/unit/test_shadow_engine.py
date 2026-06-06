"""First-principles 결정론 검증 — 4-tier shadow portfolio 엔진 (F-6).

LLM→코드 이주라 old↔new diff 불가 → 합성 fixture 로 정확한 state/trade 산출 단언.
entry / 30일 exit / falsifier exit / rebalance / 재현성 / 가격 미가용 / NAV mark /
분기 rollover / serde 커버.
"""
from __future__ import annotations

import pytest

from domains.audit_integrity.application.run_daily_update import (
    DailyInputs,
    EngineConfig,
    run_daily_update,
)
from domains.audit_integrity.domain.rules import (
    deterministic_random_k,
    select_top_k_catalyst_tickers,
)
from domains.audit_integrity.domain.state import ShadowPortfolioState

pytestmark = pytest.mark.unit


def _tier(name, *, cash, holdings=None, nav=100_000_000, closed=0, last_rebal=None, qh=None):
    return {
        "name": name,
        "initial_capital_krw": 100_000_000,
        "cash_krw": cash,
        "current_nav_krw": nav,
        "cumulative_return_pct": round(nav / 100_000_000 - 1, 6),
        "current_holdings": holdings or [],
        "closed_trades": closed,
        "last_rebalance_date": last_rebal,
        "quarterly_history": qh or [],
    }


def _state(tiers, snapshots=None):
    return ShadowPortfolioState.from_dict(
        {
            "schema": "investment-shadow-portfolio-state-v1",
            "init_date": "2026-01-02",
            "tiers": tiers,
            "daily_snapshots": snapshots or {},
        }
    )


def _empty_state():
    return _state(
        {
            "tier_0_passive_index": _tier("idx", cash=100_000_000),
            "tier_1_mechanical": _tier("mech", cash=100_000_000),
            "tier_2_llm_filtered": _tier("llm", cash=100_000_000),
            "tier_3_random": _tier("rand", cash=100_000_000),
        }
    )


def _prices(mapping):
    def price_for(t):
        p = mapping.get(t)
        return (p, f"Yahoo@2026-05-15={t}:{p}") if p is not None else (None, None)

    return price_for


def _inputs(**kw):
    base = dict(
        date="2026-05-15",
        tier0_tickers=("US:SPY", "KR:069500"),
        tier1_candidates=(),
        tier1_active_catalysts=frozenset(),
        tier2_recs=(),
        tier2_falsifier_triggered=frozenset(),
        tier3_pool=(),
    )
    base.update(kw)
    return DailyInputs(**base)


# ----------------------------------------------------------------------
# rules
# ----------------------------------------------------------------------


def test_select_top_k_primary_only_in_order():
    cats = [
        {"ticker": "KR:1", "trigger_class": "a_type"},
        {"ticker": "KR:2", "trigger_class": "d_type"},  # d_type 제외
        {"ticker": "KR:3", "trigger_class": "b_type"},
        {"ticker": "KR:1", "trigger_class": "b_type"},  # dedup
    ]
    assert select_top_k_catalyst_tickers(cats, 5) == ["KR:1", "KR:3"]
    assert select_top_k_catalyst_tickers(cats, 1) == ["KR:1"]


def test_deterministic_random_reproducible():
    pool = [f"KR:{i:06d}" for i in range(20)]
    a = deterministic_random_k(pool, 5, "2026-05-15")
    b = deterministic_random_k(pool, 5, "2026-05-15")
    c = deterministic_random_k(pool, 5, "2026-05-16")
    assert a == b  # 같은 날 → 동일
    assert len(a) == 5 and a == sorted(a)
    assert a != c  # 다른 날 → 다름 (사실상)


# ----------------------------------------------------------------------
# entry / NAV
# ----------------------------------------------------------------------


def test_entry_equal_weight_and_size_pct():
    st = _empty_state()
    res = run_daily_update(
        st,
        _inputs(
            tier1_candidates=("KR:000001", "KR:000002"),
            tier1_active_catalysts=frozenset({"KR:000001", "KR:000002"}),
            tier2_recs=(("KR:000003", 0.10),),
            tier3_pool=("KR:000001", "KR:000002"),
        ),
        EngineConfig(),
        _prices({"US:SPY": 500000, "KR:069500": 25000, "KR:000001": 10000, "KR:000002": 20000, "KR:000003": 5000}),
    )
    t = res.state.tiers
    assert {h.ticker for h in t["tier_0_passive_index"].holdings} == {"US:SPY", "KR:069500"}
    assert all(abs(h.weight - 0.5) < 1e-6 for h in t["tier_0_passive_index"].holdings)
    assert all(abs(h.weight - 0.2) < 1e-6 for h in t["tier_1_mechanical"].holdings)  # 1/K, K=5
    h2 = t["tier_2_llm_filtered"].holdings[0]
    assert abs(h2.weight - 0.10) < 1e-6  # size_pct
    assert res.closed_trades == []
    assert len(res.citations) == 5


def test_nav_marks_to_market_after_price_move():
    st = _state(
        {
            "tier_0_passive_index": _tier(
                "idx", cash=0, nav=100_000_000,
                holdings=[
                    {"ticker": "US:SPY", "qty": 100, "avg_cost_krw": 500000, "weight": 0.5, "entry_date": "2026-05-14"},
                    {"ticker": "KR:069500", "qty": 2000, "avg_cost_krw": 25000, "weight": 0.5, "entry_date": "2026-05-14"},
                ],
            ),
            "tier_1_mechanical": _tier("m", cash=100_000_000),
            "tier_2_llm_filtered": _tier("l", cash=100_000_000),
            "tier_3_random": _tier("r", cash=100_000_000),
        },
        snapshots={"2026-05-14": {"tier_0_passive_index": 100_000_000}},
    )
    # SPY +4% → 52M, KR flat 50M → nav 102M, drift 0.0196 < 0.05 (no rebalance)
    res = run_daily_update(st, _inputs(), EngineConfig(), _prices({"US:SPY": 520000, "KR:069500": 25000}))
    t0 = res.state.tiers["tier_0_passive_index"]
    assert abs(t0.current_nav_krw - 102_000_000) < 1
    assert abs(t0.cumulative_return_pct - 0.02) < 1e-6
    assert t0.last_rebalance_date is None  # drift 미달 → rebalance 안 함


# ----------------------------------------------------------------------
# exits
# ----------------------------------------------------------------------


def test_tier0_rebalance_on_drift():
    st = _state(
        {
            "tier_0_passive_index": _tier(
                "idx", cash=0,
                holdings=[
                    {"ticker": "US:SPY", "qty": 100, "avg_cost_krw": 500000, "weight": 0.5, "entry_date": "2026-05-10"},
                    {"ticker": "KR:069500", "qty": 2000, "avg_cost_krw": 25000, "weight": 0.5, "entry_date": "2026-05-10"},
                ],
            ),
            "tier_1_mechanical": _tier("m", cash=100_000_000),
            "tier_2_llm_filtered": _tier("l", cash=100_000_000),
            "tier_3_random": _tier("r", cash=100_000_000),
        },
    )
    # SPY +30% → 65M, nav 115M, SPY weight 0.565 → drift 0.065 > 0.05 → rebalance
    res = run_daily_update(st, _inputs(), EngineConfig(), _prices({"US:SPY": 650000, "KR:069500": 25000}))
    t0 = res.state.tiers["tier_0_passive_index"]
    reb = [c for c in res.closed_trades if c.reason == "rebalance"]
    assert len(reb) == 2
    assert t0.last_rebalance_date == "2026-05-15"
    assert all(abs(h.weight - 0.5) < 1e-6 for h in t0.holdings)  # 재진입 50/50


def test_tier1_catalyst_inactive_exit():
    st = _state(
        {
            "tier_0_passive_index": _tier("i", cash=100_000_000),
            "tier_1_mechanical": _tier(
                "m", cash=80_000_000,
                holdings=[{"ticker": "KR:000001", "qty": 2000, "avg_cost_krw": 10000, "weight": 0.2, "entry_date": "2026-04-01"}],
            ),
            "tier_2_llm_filtered": _tier("l", cash=100_000_000),
            "tier_3_random": _tier("r", cash=100_000_000),
        }
    )
    # 보유 44일, 오늘 catalyst 없음 → catalyst_inactive 청산
    res = run_daily_update(
        st, _inputs(tier1_active_catalysts=frozenset()), EngineConfig(), _prices({"KR:000001": 11000})
    )
    exits = [c for c in res.closed_trades if c.reason == "catalyst_inactive"]
    assert len(exits) == 1 and exits[0].ticker == "KR:000001"
    assert exits[0].return_pct == pytest.approx(0.1)  # 11000/10000-1
    assert res.state.tiers["tier_1_mechanical"].holdings == []


def test_tier1_kept_if_catalyst_active():
    st = _state(
        {
            "tier_0_passive_index": _tier("i", cash=100_000_000),
            "tier_1_mechanical": _tier(
                "m", cash=80_000_000,
                holdings=[{"ticker": "KR:000001", "qty": 2000, "avg_cost_krw": 10000, "weight": 0.2, "entry_date": "2026-04-01"}],
            ),
            "tier_2_llm_filtered": _tier("l", cash=100_000_000),
            "tier_3_random": _tier("r", cash=100_000_000),
        }
    )
    res = run_daily_update(
        st,
        _inputs(tier1_candidates=("KR:000001",), tier1_active_catalysts=frozenset({"KR:000001"})),
        EngineConfig(),
        _prices({"KR:000001": 11000}),
    )
    assert [h.ticker for h in res.state.tiers["tier_1_mechanical"].holdings] == ["KR:000001"]
    assert res.closed_trades == []


def test_tier2_falsifier_exit():
    st = _state(
        {
            "tier_0_passive_index": _tier("i", cash=100_000_000),
            "tier_1_mechanical": _tier("m", cash=100_000_000),
            "tier_2_llm_filtered": _tier(
                "l", cash=90_000_000,
                holdings=[{"ticker": "KR:000003", "qty": 2000, "avg_cost_krw": 5000, "weight": 0.1, "entry_date": "2026-05-10"}],
            ),
            "tier_3_random": _tier("r", cash=100_000_000),
        }
    )
    res = run_daily_update(
        st,
        _inputs(tier2_falsifier_triggered=frozenset({"KR:000003"})),
        EngineConfig(),
        _prices({"KR:000003": 4000}),
    )
    exits = [c for c in res.closed_trades if c.reason == "falsifier_triggered"]
    assert len(exits) == 1 and exits[0].ticker == "KR:000003"
    assert exits[0].return_pct == pytest.approx(-0.2)
    assert res.state.tiers["tier_2_llm_filtered"].holdings == []


def test_tier3_30day_exit():
    st = _state(
        {
            "tier_0_passive_index": _tier("i", cash=100_000_000),
            "tier_1_mechanical": _tier("m", cash=100_000_000),
            "tier_2_llm_filtered": _tier("l", cash=100_000_000),
            "tier_3_random": _tier(
                "r", cash=80_000_000,
                holdings=[{"ticker": "KR:000009", "qty": 1000, "avg_cost_krw": 20000, "weight": 0.2, "entry_date": "2026-04-01"}],
            ),
        }
    )
    res = run_daily_update(st, _inputs(tier3_pool=()), EngineConfig(), _prices({"KR:000009": 21000}))
    exits = [c for c in res.closed_trades if c.reason == "30_day_holding_max"]
    assert len(exits) == 1 and exits[0].ticker == "KR:000009"


# ----------------------------------------------------------------------
# G8 price missing / Mode C
# ----------------------------------------------------------------------


def test_price_missing_holds_entry_with_warning():
    st = _empty_state()
    res = run_daily_update(
        st,
        _inputs(tier1_candidates=("KR:000001",), tier1_active_catalysts=frozenset({"KR:000001"})),
        EngineConfig(),
        _prices({}),  # 모든 가격 미가용
    )
    assert res.state.tiers["tier_1_mechanical"].holdings == []  # 진입 보류
    assert any("진입 보류" in w for w in res.warnings)
    assert res.citations == []  # Mode C 신호 (main 이 snapshot 미저장)


# ----------------------------------------------------------------------
# quarter rollover
# ----------------------------------------------------------------------


def test_quarter_rollover_appends_history():
    # Q1 마지막 snapshot 들 + Q2 첫날 update → Q1 return 이 quarterly_history 에 append
    st = _state(
        {
            "tier_0_passive_index": _tier("i", cash=100_000_000),
            "tier_1_mechanical": _tier("m", cash=100_000_000),
            "tier_2_llm_filtered": _tier("l", cash=100_000_000),
            "tier_3_random": _tier("r", cash=100_000_000),
        },
        snapshots={
            "2026-03-02": {"tier_0_passive_index": 100_000_000, "tier_1_mechanical": 100_000_000,
                           "tier_2_llm_filtered": 100_000_000, "tier_3_random": 100_000_000},
            "2026-03-31": {"tier_0_passive_index": 110_000_000, "tier_1_mechanical": 100_000_000,
                           "tier_2_llm_filtered": 100_000_000, "tier_3_random": 100_000_000},
        },
    )
    res = run_daily_update(st, _inputs(date="2026-04-01"), EngineConfig(), _prices({"US:SPY": 500000, "KR:069500": 25000}))
    qh = res.state.tiers["tier_0_passive_index"].quarterly_history
    assert qh == [{"quarter": "2026-Q1", "return_pct": pytest.approx(0.10)}]
    # 2026-04-01 snapshot 기록됨
    assert "2026-04-01" in res.state.daily_snapshots


# ----------------------------------------------------------------------
# serde round-trip
# ----------------------------------------------------------------------


def test_state_serde_roundtrip():
    st = _empty_state()
    run_daily_update(
        st,
        _inputs(tier1_candidates=("KR:000001",), tier1_active_catalysts=frozenset({"KR:000001"})),
        EngineConfig(),
        _prices({"US:SPY": 500000, "KR:069500": 25000, "KR:000001": 10000}),
    )
    d = st.to_dict()
    again = ShadowPortfolioState.from_dict(d).to_dict()
    assert again == d  # to_dict → from_dict → to_dict 안정
