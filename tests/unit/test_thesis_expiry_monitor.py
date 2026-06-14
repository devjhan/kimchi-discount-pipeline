"""
tests/unit/test_thesis_expiry_monitor.py — Stage 5d thesis_expiry_monitor 단위 검증.

Covered:
    - tier 분류: ok / notice / warn / expired / overdue / unmeasurable
    - days_remaining 산식 정확성
    - missing time_horizon_months → unmeasurable
    - status=closed thesis → load_open_thesis 에서 제외
    - render_expiry_md 본문 markdown 필드 포함 확인
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta


from domains.risk_engine import thesis_expiry_monitor as tem
from infrastructure._common.utils import KST


DEFAULT_TIERS = {
    "notice_days":   90,
    "warn_days":     30,
    "expired_days":   0,
    "overdue_days": -30,
}


def _today_offset(days: int) -> str:
    return (datetime.now(KST) + timedelta(days=days)).strftime("%Y-%m-%d")


def _make_position(
    entry_date: str,
    horizon_months: float,
    *,
    ticker: str = "KR:003550",
    status: str = "open",
) -> dict:
    return {
        "ticker": ticker,
        "name": "LG",
        "entry_date": entry_date,
        "status": status,
        "thesis": {
            "time_horizon_months": horizon_months,
            "falsifier": {"category": "metric_trigger", "spec": {}},
        },
    }


def test_tier_ok_far_from_expiry():
    # entry 오늘, horizon 24개월 → days_remaining ≈ 730
    pos = _make_position(_today_offset(0), 24)
    today = _today_offset(0)
    rec = tem.compute_expiry(pos, today=today, tiers=DEFAULT_TIERS)
    assert rec.tier == "ok"
    assert rec.needs_user_decision is False
    assert rec.days_remaining > DEFAULT_TIERS["notice_days"]


def test_tier_notice_at_60_days_remaining():
    # 60 일 = notice (>30 but <=90)
    horizon_months = 60 / tem.DAYS_PER_MONTH
    pos = _make_position(_today_offset(0), horizon_months)
    rec = tem.compute_expiry(pos, today=_today_offset(0), tiers=DEFAULT_TIERS)
    assert rec.tier == "notice"
    assert rec.needs_user_decision is False


def test_tier_warn_at_15_days_remaining():
    horizon_months = 15 / tem.DAYS_PER_MONTH
    pos = _make_position(_today_offset(0), horizon_months)
    rec = tem.compute_expiry(pos, today=_today_offset(0), tiers=DEFAULT_TIERS)
    assert rec.tier == "warn"
    assert rec.needs_user_decision is True
    assert 14 <= rec.days_remaining <= 16


def test_tier_expired_when_zero_days():
    # entry T-N개월, horizon 정확히 N개월 → expiry == today, days_remaining == 0
    horizon_months = 6.0
    days_offset = int(round(horizon_months * tem.DAYS_PER_MONTH))
    pos = _make_position(_today_offset(-days_offset), horizon_months)
    rec = tem.compute_expiry(pos, today=_today_offset(0), tiers=DEFAULT_TIERS)
    # rounding 문제로 days_remaining 가 -1 ~ +1 사이 → expired 또는 인접 tier
    assert rec.tier in ("expired", "warn", "overdue")
    if rec.tier == "expired":
        assert rec.days_remaining == 0


def test_tier_overdue_past_expiry():
    # entry T-25개월, horizon 24개월 → days_remaining ≈ -30 → overdue (boundary)
    pos = _make_position(_today_offset(-int(25 * tem.DAYS_PER_MONTH)), 24)
    rec = tem.compute_expiry(pos, today=_today_offset(0), tiers=DEFAULT_TIERS)
    assert rec.tier == "overdue"
    assert rec.needs_user_decision is True
    assert rec.days_remaining < 0


def test_missing_horizon_unmeasurable():
    pos = {
        "ticker": "KR:000000",
        "name": "X",
        "entry_date": "2026-01-01",
        "status": "open",
        "thesis": {"falsifier": {"category": "metric_trigger", "spec": {}}},
    }
    rec = tem.compute_expiry(pos, today=_today_offset(0), tiers=DEFAULT_TIERS)
    assert rec.tier == "unmeasurable"
    assert rec.needs_user_decision is True


def test_load_open_thesis_filters_closed(isolated_workspace):
    pdir = isolated_workspace["positions_dir"]
    open_dir = pdir / "KR_003550"
    closed_dir = pdir / "KR_000660"
    open_dir.mkdir()
    closed_dir.mkdir()

    (open_dir / "thesis.json").write_text(
        json.dumps(_make_position("2026-01-01", 18, ticker="KR:003550")), encoding="utf-8"
    )
    (closed_dir / "thesis.json").write_text(
        json.dumps(
            _make_position("2026-01-01", 18, ticker="KR:000660", status="closed")
        ),
        encoding="utf-8",
    )

    positions, warnings = tem.load_open_thesis(pdir)
    assert len(positions) == 1
    assert positions[0]["ticker"] == "KR:003550"
    assert warnings == []


def test_render_expiry_md_includes_fields():
    rec = tem.ExpiryRecord(
        ticker="KR:003550",
        name="LG",
        entry_date="2026-01-15",
        horizon_months=18.0,
        expiry_date="2027-07-13",
        days_remaining=15,
        tier="warn",
        rationale="만료 임박",
        needs_user_decision=True,
    )
    body = tem.render_expiry_md(rec, today="2026-05-11")
    assert "KR:003550" in body
    assert "warn" in body
    assert "2027-07-13" in body
    assert "days_remaining" in body
    assert "G9" in body  # disclaimer 포함


def test_classify_tier_boundary_negative_30():
    # exactly T-30 = overdue boundary
    assert tem._classify_tier(-30, DEFAULT_TIERS) == "overdue"
    assert tem._classify_tier(-31, DEFAULT_TIERS) == "overdue"
    assert tem._classify_tier(-1, DEFAULT_TIERS) == "overdue"


def test_classify_tier_boundary_positive():
    assert tem._classify_tier(0, DEFAULT_TIERS) == "expired"
    assert tem._classify_tier(1, DEFAULT_TIERS) == "warn"
    assert tem._classify_tier(30, DEFAULT_TIERS) == "warn"
    assert tem._classify_tier(31, DEFAULT_TIERS) == "notice"
    assert tem._classify_tier(90, DEFAULT_TIERS) == "notice"
    assert tem._classify_tier(91, DEFAULT_TIERS) == "ok"
