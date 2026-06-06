"""positions_sync.sync_account 특성화 테스트 — KisAccountPort 주입 + 커버리지 보강.

기존 positions_sync 직접 커버 부재 → 본 테스트가 KIS read 6 endpoint 오케스트레이션의
AccountSummary 산출을 고정한다. fake KisAccountPort 주입 = port seam 테스트 용이성 검증
(+ G9c: order 메서드 부재 port 로 sync 동작).
"""
from __future__ import annotations

from typing import Any

import pytest

from domains.risk_engine import positions_sync
from domains.risk_engine.positions_sync import sync_account
from domains.risk_engine.ports.kis_account import KisAccountPort

_ENV = {"KIS_APP_KEY": "k", "KIS_APP_SECRET": "s", "KIS_ACCOUNT_NUMBER": "12345678-01"}
_TS = "2026-05-15T15:30:00+09:00"


class _FakeKisAccount:
    """KisAccountPort stub — canned KIS read 응답 (order 메서드 부재)."""

    def issue_access_token(self, env: dict[str, str]) -> str:
        return "tok"

    def fetch_account_balance(self, **kwargs: Any) -> dict[str, Any]:
        return {
            "positions": [
                {
                    "pdno": "005930", "prdt_name": "삼성전자", "hldg_qty": "10",
                    "pchs_avg_pric": "70000", "prpr": "80000", "evlu_amt": "800000",
                    "pchs_amt": "700000", "evlu_pfls_amt": "100000", "evlu_pfls_rt": "14.28",
                }
            ],
            "summary": [
                {"tot_evlu_amt": "5000000", "dnca_tot_amt": "1000000", "evlu_pfls_smtl_amt": "100000"}
            ],
        }

    def fetch_buyable_amount(self, **kwargs: Any) -> dict[str, Any]:
        return {"ord_psbl_cash": "950000"}

    def fetch_account_assets(self, **kwargs: Any) -> dict[str, Any]:
        return {"totals": {"tot_asst_amt": "6000000"}}

    def fetch_realized_pnl(self, **kwargs: Any) -> dict[str, Any]:
        return {
            "positions": [{"pdno": "005930", "rlzt_pfls": "50000"}],
            "summary": [{"rlzt_pfls_smtl": "50000"}],
        }

    def fetch_sellable_qty(self, *, stock_code: str, **kwargs: Any) -> dict[str, Any]:
        return {"nrcvb_buy_qty": "10"}


@pytest.fixture(autouse=True)
def _gate_open(monkeypatch: pytest.MonkeyPatch) -> None:
    """G9b 정책 게이트 open + 결정론 ts."""
    monkeypatch.setattr(positions_sync, "kis_read_only_enabled", lambda: (True, None))
    monkeypatch.setattr(positions_sync, "now_iso_kst", lambda: _TS)


@pytest.mark.unit
def test_sync_account_summary_from_kis_reads() -> None:
    """fake port 6 read → AccountSummary 필드 정확."""
    summary = sync_account(date="2026-05-15", env=_ENV, account=_FakeKisAccount())
    assert summary.sync_status == "ok"
    assert summary.total_assets_krw == 5000000.0
    assert summary.cash_krw == 1000000.0
    assert summary.eval_pnl_total == 100000.0
    assert summary.buyable_cash_krw == 950000.0
    assert summary.realized_pnl_period == 50000.0
    assert summary.holdings_count == 1
    h = summary.holdings[0]
    assert h["ticker"] == "005930"
    assert h["quantity"] == 10
    assert h["avg_price"] == 70000.0
    assert h["current_price"] == 80000.0
    assert h["sellable_qty"] == 10
    assert h["realized_pnl_period"] == 50000.0
    assert summary.citations  # G7 — 비어있지 않음


@pytest.mark.unit
def test_sync_account_skipped_when_gate_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """정책 게이트 off → sync_status='skipped' (KIS 호출 0)."""
    monkeypatch.setattr(positions_sync, "kis_read_only_enabled", lambda: (False, "disabled"))
    summary = sync_account(date="2026-05-15", env=_ENV, account=_FakeKisAccount())
    assert summary.sync_status == "skipped"
    assert summary.skip_reason == "disabled"


@pytest.mark.unit
def test_fake_satisfies_port_and_surface_is_read_only() -> None:
    """G9c — KisAccountPort surface = 정확히 6 read 메서드 (order/submit/cancel 부재)."""
    assert isinstance(_FakeKisAccount(), KisAccountPort)
    methods = {
        m for m in dir(KisAccountPort)
        if not m.startswith("_") and callable(getattr(KisAccountPort, m, None))
    }
    assert methods == {
        "issue_access_token",
        "fetch_account_balance",
        "fetch_buyable_amount",
        "fetch_account_assets",
        "fetch_realized_pnl",
        "fetch_sellable_qty",
    }
