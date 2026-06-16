"""audit_integrity main + io 통합 — state store / trail loader / trade-log / Mode B·C."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import domains.audit_integrity.main as main_mod
from domains.audit_integrity import _boundary
from domains.audit_integrity.io.price_source import PriceSource

pytestmark = pytest.mark.unit

DATE = "2026-05-15"
PRICES = {
    "US:SPY": 500000.0, "KR:069500": 25000.0,
    "KR:000001": 10000.0, "KR:000003": 5000.0, "KR:000009": 20000.0,
}


def _init_state_dict():
    def tier(name, cash=100_000_000, holdings=None, closed=0):
        return {
            "name": name, "initial_capital_krw": 100_000_000, "cash_krw": cash,
            "current_nav_krw": 100_000_000, "cumulative_return_pct": 0.0,
            "current_holdings": holdings or [], "closed_trades": closed,
            "last_rebalance_date": None, "quarterly_history": [],
        }

    return {
        "schema": "investment-shadow-portfolio-state-v1", "init_date": "2026-05-01",
        "tiers": {
            "tier_0_passive_index": tier("idx"),
            "tier_1_mechanical": tier("mech"),
            "tier_2_llm_filtered": tier("llm"),
            "tier_3_random": tier(
                "rand", cash=80_000_000,
                holdings=[{"ticker": "KR:000009", "qty": 1000, "avg_cost_krw": 20000, "weight": 0.2, "entry_date": "2026-04-01"}],
            ),
        },
        "daily_snapshots": {},
    }


def _state_file(audit: Path) -> Path:
    return audit / "shadow-portfolio" / "state.json"


def _write_state(audit: Path, data: dict) -> Path:
    p = _state_file(audit)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


@pytest.fixture
def env_dirs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    audit = tmp_path / "audit"
    trail = tmp_path / "trail"
    audit.mkdir()
    trail.mkdir()
    monkeypatch.setenv("AUDIT_DIR", str(audit))
    monkeypatch.setenv("TRAIL_TODAY", str(trail))
    monkeypatch.setattr(_boundary, "load_env", lambda *a, **k: {})
    monkeypatch.setattr(_boundary, "resolve_allow_yahoo_fallback", lambda v: True)
    monkeypatch.setattr(
        PriceSource, "price_for",
        lambda self, t: ((PRICES[t], f"Yahoo@{DATE}={t}") if t in PRICES else (None, None)),
    )
    return audit, trail


def _write_trail(trail: Path):
    (trail / "01-universe.json").write_text(json.dumps({
        "entries": [{"ticker": "KR:000001"}, {"ticker": "KR:000003"}]
    }), encoding="utf-8")
    (trail / "02-quality-filter.json").write_text(json.dumps({
        "verdicts": [{"ticker": "KR:000001", "verdict": "pass"}, {"ticker": "KR:000003", "verdict": "pass"}]
    }), encoding="utf-8")
    (trail / "03-catalyst-events.json").write_text(json.dumps({
        "catalysts": [{"ticker": "KR:000001", "trigger_class": "a_type", "catalyst_type": "x"}]
    }), encoding="utf-8")
    (trail / "05-sizing-recommendation.json").write_text(json.dumps({
        "recommendations": [{"ticker": "KR:000003", "name": "n", "verdict": "size_recommended", "size_pct_of_portfolio": 0.10}]
    }), encoding="utf-8")
    (trail / f"event-trigger-status-{DATE}.json").write_text(json.dumps({
        "records": [{"ticker": "KR:000009", "signal": "triggered"}]
    }), encoding="utf-8")


def test_main_mode_b_missing_state_exits_2(env_dirs):
    assert main_mod.main(["--date", DATE]) == 2  # state 부재


def test_main_daily_update_writes_state_and_trades(env_dirs):
    audit, trail = env_dirs
    _write_state(audit, _init_state_dict())
    _write_trail(trail)

    assert main_mod.main(["--date", DATE]) == 0

    state = json.loads(_state_file(audit).read_text(encoding="utf-8"))
    tiers = state["tiers"]
    # tier_1: KR:000001 진입
    assert [h["ticker"] for h in tiers["tier_1_mechanical"]["current_holdings"]] == ["KR:000001"]
    # tier_2: KR:000003 size_pct 진입
    assert [h["ticker"] for h in tiers["tier_2_llm_filtered"]["current_holdings"]] == ["KR:000003"]
    # tier_3: KR:000009 는 falsifier 와 무관하지만 보유 44일 → 30일 만료 청산
    t3_holdings = [h["ticker"] for h in tiers["tier_3_random"]["current_holdings"]]
    assert "KR:000009" not in t3_holdings
    assert DATE in state["daily_snapshots"]

    # trade-log: tier_3 청산 CSV 기록
    csv3 = audit / "shadow-portfolio" / "trade-log-tier_3_random.csv"
    assert csv3.exists()
    body = csv3.read_text(encoding="utf-8").strip().splitlines()
    assert body[0].startswith("trade_id,ticker")
    assert any("30_day_holding_max" in line for line in body[1:])


def test_main_mode_c_no_prices_skips_save(env_dirs, monkeypatch):
    audit, trail = env_dirs
    _write_state(audit, _init_state_dict())
    _write_trail(trail)
    # 모든 가격 미가용 → citations 0 → Mode C (snapshot 미저장)
    monkeypatch.setattr(PriceSource, "price_for", lambda self, t: (None, None))
    before = _state_file(audit).read_text(encoding="utf-8")
    assert main_mod.main(["--date", DATE]) == 0
    after = _state_file(audit).read_text(encoding="utf-8")
    assert before == after  # state 보존 (snapshot 미저장)
