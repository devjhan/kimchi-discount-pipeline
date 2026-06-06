"""catalyst detector / orchestrator 단위 테스트 — 구 6 detector 의 0-coverage gap 보강.

from_spec 파싱 · enabled skip · G14 universe 필터 · G15 d_type orphan ·
nav narrowing (구 dead path) 직접 커버.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from domains.catalyst.application.scan_catalysts import (
    augment_d_type_into_primary,
    scan_catalysts,
)
from domains.catalyst.detectors.base import (
    CatalystDetector,
    DetectContext,
    DetectResult,
)
from domains.catalyst.detectors.factory import build_detector, build_detectors
from domains.catalyst.detectors.nav_discount_narrowing import NavDiscountNarrowingDetector
from domains.catalyst.domain.event import CatalystEvent


def _ctx(universe=None, market=None) -> DetectContext:
    return DetectContext(
        env={},
        universe=universe or {},
        universe_market=market or {},
        date="2026-05-15",
        fetched_at="2026-05-15T15:30:00+09:00",
        allow_yahoo=False,
    )


def _event(ticker: str, trigger_class: str, ctype: str, cid: str) -> CatalystEvent:
    return CatalystEvent(
        catalyst_id=cid,
        ticker=ticker,
        name=ticker,
        catalyst_type=ctype,
        trigger_class=trigger_class,
        detected_at="t",
        source_citation="DART@t=v",
        metadata={},
    )


# ----------------------------------------------------------------------
# factory / from_spec
# ----------------------------------------------------------------------


@pytest.mark.unit
def test_factory_unknown_type_raises() -> None:
    with pytest.raises(ValueError, match="unknown detector type"):
        build_detector({"name": "x", "type": "no_such_detector"})


@pytest.mark.unit
def test_factory_missing_fields_raise() -> None:
    with pytest.raises(ValueError, match="missing 'type'"):
        build_detector({"name": "x"})
    with pytest.raises(ValueError, match="missing 'name'"):
        build_detector({"type": "treasury_share_cancellation"})


@pytest.mark.unit
def test_from_spec_parses_thresholds() -> None:
    specs = [
        {"name": "t", "type": "treasury_share_cancellation", "lookback_days": 45},
        {"name": "n", "type": "nav_discount_narrowing", "delta_threshold": -0.07, "lookback_days": 90},
    ]
    built = build_detectors(specs)
    assert built[0].lookback_days == 45
    assert isinstance(built[1], NavDiscountNarrowingDetector)
    assert built[1].delta_threshold == -0.07


# ----------------------------------------------------------------------
# orchestrator — enabled skip / quality marker
# ----------------------------------------------------------------------


class _StubDetector(CatalystDetector):
    def __init__(self, name: str, enabled: bool, events: tuple[CatalystEvent, ...]):
        self.name = name
        self.enabled = enabled
        self._events = events

    @classmethod
    def from_spec(cls, spec):  # pragma: no cover - not used
        raise NotImplementedError

    def detect(self, ctx: DetectContext) -> DetectResult:
        return DetectResult(self._events, ())


@pytest.mark.unit
def test_scan_skips_disabled_detector() -> None:
    on = _StubDetector("on", True, (_event("KR:1", "a_type", "treasury_share_cancellation", "c1"),))
    off = _StubDetector("off", False, (_event("KR:2", "a_type", "spin_off_announcement", "c2"),))
    result, _ = scan_catalysts(
        detectors=[on, off], ctx=_ctx(universe={"KR:1": "a", "KR:2": "b"}), quality_pass=set(), dry_run=False
    )
    tickers = {c.ticker for c in result.catalysts}
    assert tickers == {"KR:1"}  # disabled detector 산출 제외


@pytest.mark.unit
def test_dry_run_runs_no_detectors() -> None:
    on = _StubDetector("on", True, (_event("KR:1", "a_type", "x", "c1"),))
    result, warns = scan_catalysts(
        detectors=[on], ctx=_ctx(universe={"KR:1": "a"}), quality_pass=set(), dry_run=True
    )
    assert result.catalysts == ()
    assert result.stats["dry_run"] is True


# ----------------------------------------------------------------------
# G15 augment / orphan
# ----------------------------------------------------------------------


@pytest.mark.unit
def test_augment_d_type_orphan_excluded() -> None:
    events = [
        _event("KR:1", "a_type", "treasury_share_cancellation", "p1"),
        _event("KR:1", "d_type", "activist_5pct_filing", "d1"),  # 결합 → augment
        _event("KR:2", "d_type", "activist_5pct_filing", "d2"),  # 단독 → orphan
    ]
    primary, orphans = augment_d_type_into_primary(events)
    assert [p.ticker for p in primary] == ["KR:1"]
    assert primary[0].metadata["d_type_augments"][0]["catalyst_id"] == "d1"
    assert [o.ticker for o in orphans] == ["KR:2"]


# ----------------------------------------------------------------------
# nav narrowing — 구 dead path 직접 커버 (event 생성 + warning)
# ----------------------------------------------------------------------


@pytest.mark.unit
def test_nav_detector_empty_holdings_warns(monkeypatch, tmp_path: Path) -> None:
    # nav-history store 격리 (empty) → config 목록도 store(list_parents) 도 비어 skip.
    monkeypatch.setenv("NAV_HISTORY_DIR", str(tmp_path))
    det = NavDiscountNarrowingDetector.from_spec(
        {"name": "nav", "type": "nav_discount_narrowing"}
    )
    res = det.detect(_ctx(universe={"KR:003550": "LG"}))
    assert res.events == ()
    assert any("holding_companies_subsidiaries manual map 비어있음" in w for w in res.warnings)


@pytest.mark.unit
def test_nav_detector_narrowing_emits_event(monkeypatch, tmp_path: Path) -> None:
    from domains._shared import nav_history

    monkeypatch.setenv("NAV_HISTORY_DIR", str(tmp_path))
    parent = "KR:003550"
    nav_history.append_nav_snapshot(
        parent, "2026-04-01", parent_mcap_krw=1e12, nav_sum_krw=3e12, premium_pct=-0.66, citations=["KIS@2026-04-01=a"]
    )
    nav_history.append_nav_snapshot(
        parent, "2026-05-01", parent_mcap_krw=1.2e12, nav_sum_krw=3e12, premium_pct=-0.60, citations=["KIS@2026-05-01=b"]
    )
    det = NavDiscountNarrowingDetector.from_spec(
        {
            "name": "nav",
            "type": "nav_discount_narrowing",
            "delta_threshold": -0.05,
            "lookback_days": 90,
            "holding_companies": [parent],
        }
    )
    res = det.detect(_ctx(universe={parent: "LG"}))
    assert len(res.events) == 1
    ev = res.events[0]
    assert ev.catalyst_type == "nav_discount_narrowing"
    assert ev.trigger_class == "a_type"
    assert ev.detected_at == "2026-05-15T15:30:00+09:00"  # well-formed (구 dead path 교정)
    assert ev.metadata["delta"] == pytest.approx(0.06)
    assert ev.source_citation == "KIS@2026-04-01=a"


@pytest.mark.unit
def test_nav_detector_discovers_parents_from_store(monkeypatch, tmp_path: Path) -> None:
    """config holding_companies 부재 시 nav_history.list_parents() 로 parent 자동 발견 (B-2)."""
    from domains._shared import nav_history

    monkeypatch.setenv("NAV_HISTORY_DIR", str(tmp_path))
    parent = "KR:003550"
    nav_history.append_nav_snapshot(parent, "2026-04-01", parent_mcap_krw=1e12, nav_sum_krw=3e12, premium_pct=-0.66, citations=["a"])
    nav_history.append_nav_snapshot(parent, "2026-05-01", parent_mcap_krw=1.2e12, nav_sum_krw=3e12, premium_pct=-0.58, citations=["b"])
    # holding_companies 미지정 → list_parents() 가 store 의 parent 자동 발견 후 발화.
    det = NavDiscountNarrowingDetector.from_spec(
        {"name": "nav", "type": "nav_discount_narrowing", "delta_threshold": -0.05, "lookback_days": 90}
    )
    res = det.detect(_ctx(universe={parent: "LG"}))
    assert len(res.events) == 1
    assert res.events[0].ticker == parent
