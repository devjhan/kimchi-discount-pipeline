"""Phase 2.1 — intake(순수) + analyze(engine 위임) 단위 테스트."""
from __future__ import annotations

import pytest

from domains.policy.application.analyze import run_analysis
from domains.policy.application.intake import build_triggers
from domains.policy.domain.research_result import ResearchOutput
from domains.policy.domain.trigger import Trigger


@pytest.mark.unit
def test_intake_empty_returns_empty() -> None:
    assert build_triggers([], now_iso="2026-06-01T16:00:00+09:00") == ()


@pytest.mark.unit
def test_intake_skips_incomplete_events() -> None:
    events = [
        {"kind": "filing", "ticker": "KR:005930", "payload_ref": "rcept_no=1"},
        {"kind": "filing", "ticker": "KR:000660"},  # payload_ref 없음 → skip
        {"ticker": "KR:111111", "payload_ref": "x"},  # kind 없음 → skip
    ]
    triggers = build_triggers(events, now_iso="2026-06-01T16:00:00+09:00")
    assert len(triggers) == 1
    assert triggers[0] == Trigger(
        kind="filing",
        ticker="KR:005930",
        payload_ref="rcept_no=1",
        detected_at="2026-06-01T16:00:00+09:00",
    )
    assert triggers[0].describe() == "filing:rcept_no=1"


class _StubEngine:
    """고정 ResearchOutput 반환 — PolicyEngine Protocol conformance."""

    def analyze(self, trigger: Trigger, *, evidence: tuple[str, ...]) -> ResearchOutput:
        return ResearchOutput(
            ticker=trigger.ticker,
            required_enrichments=("nav_discount",),
            cutoff_rules={"type": "and", "name": "c", "children": []},
            citations=("DART@2026-05-30T16:00=20260530000123",),
            rationale_ko="stub",
        )


@pytest.mark.unit
def test_engine_protocol_conformance() -> None:
    trig = Trigger(
        kind="manual", ticker="KR:005930", payload_ref="manual", detected_at="t"
    )
    out = run_analysis(trig, _StubEngine(), evidence=())
    assert isinstance(out, ResearchOutput)
    assert out.ticker == "KR:005930"
    assert out.required_enrichments == ("nav_discount",)
