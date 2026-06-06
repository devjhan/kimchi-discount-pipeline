"""tests/integration/test_thesis_sync_e2e.py — Stage 5a thesis.json 파생 round-trip golden.

F-5b writer gap 의 핵심 검증: stage4 04-thesis-candidates.json (3 falsifier 카테고리) →
thesis_sync → thesis.json 파생 → 3 monitor(5b/5c/5d)가 *실데이터* 위에서 well-formed
record 산출. LLM→코드 이주라 old↔new diff 동등성이 없으므로 first-principles golden.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from domains.risk_engine import (
    event_falsifier_linker,
    falsifier_proximity,
    thesis_expiry_monitor,
    thesis_sync,
)

pytestmark = pytest.mark.integration

DATE = "2026-05-08"  # 금요일 (거래일)


def _candidate(ticker: str, name: str, falsifier: dict) -> dict:
    return {
        "ticker": ticker,
        "name": name,
        "thesis_kind": "new_entry",
        "verdict": "accepted",
        "thesis": {
            "entry_catalyst": {"catalyst_id": f"DART-{ticker}", "catalyst_type": "treasury_share_cancellation"},
            "falsifier": falsifier,
            "time_horizon_months": 18,
            "edge_source": {"primary": ["C", "D"]},
            "asymmetry_score": {
                "downside_floor": {"krw_per_share_or_pct": "-25%", "source_citation": "DART@2026-04-30={NAV}"},
                "upside_ceiling": {"krw_per_share_or_pct": "+80%", "source_citation": "DART@2026-04-30={NAV}"},
            },
        },
        "rejection_reason": None,
        "pending_user_questions": [],
        "amendment_diff": None,
    }


def _write_candidates(trail: Path, candidates: list[dict]) -> None:
    (trail / "04-thesis-candidates.json").write_text(
        json.dumps({"schema": "investment-stage4-thesis-candidates-v1", "candidates": candidates}),
        encoding="utf-8",
    )


def _run_no_argv(monkeypatch, module, trail: Path) -> None:
    """--argv 를 안 받는 main() (falsifier_proximity / thesis_expiry) 을 sys.argv 로 구동."""
    monkeypatch.setattr(sys, "argv", ["prog", "--date", DATE, "--trail-dir", str(trail)])
    assert module.main() == 0


def test_thesis_sync_roundtrip_three_falsifier_categories(isolated_workspace, monkeypatch) -> None:
    trail = isolated_workspace["trail_today"]
    positions = isolated_workspace["positions_dir"]

    _write_candidates(
        trail,
        [
            _candidate(
                "KR:003550", "LG",
                {"categories": ["time_cap"], "items": [{"category": "time_cap", "statement": "18개월 exit", "max_months": 18}]},
            ),
            _candidate(
                "KR:000660", "SK하이닉스",
                {"categories": ["metric_trigger"], "items": [
                    {"category": "metric_trigger", "metric": "price", "threshold": 60000, "direction": "below", "statement": "60k 이하 exit"}
                ]},
            ),
            _candidate(
                "KR:005930", "삼성전자",
                {"categories": ["event_trigger"], "items": [
                    {"category": "event_trigger", "watch_catalyst_type": "treasury_share_cancellation",
                     "direction": "presence", "statement": "소각 발표 시 thesis 강화/재평가"}
                ]},
            ),
        ],
    )

    # 1) 파생
    assert thesis_sync.main(["--date", DATE, "--trail-dir", str(trail)]) == 0
    sync_env = json.loads((trail / "05a-thesis-sync.json").read_text(encoding="utf-8"))
    assert sync_env["stats"]["written"] == 3

    # 2) thesis.json 3개가 올바른 projected shape 로 생성
    cats = {}
    for tk in ("KR_003550", "KR_000660", "KR_005930"):
        tp = positions / tk / "thesis.json"
        assert tp.exists(), f"{tk}/thesis.json 미생성"
        data = json.loads(tp.read_text(encoding="utf-8"))
        assert data["status"] == "open"
        assert data["thesis"]["time_horizon_months"] == 18.0
        assert data["_provenance"]["citations"]  # G7 carry (non-empty)
        cats[tk] = data["thesis"]["falsifier"]["category"]
    assert cats == {"KR_003550": "time_cap", "KR_000660": "metric_trigger", "KR_005930": "event_trigger"}
    # metric_trigger 의 threshold→target_value 매핑 확인
    m = json.loads((positions / "KR_000660" / "thesis.json").read_text())
    assert m["thesis"]["falsifier"]["spec"]["target_value"] == 60000
    assert m["thesis"]["falsifier"]["spec"]["metric"] == "price"

    # 3) Stage 5b falsifier_proximity — 실데이터 3 position 처리
    _run_no_argv(monkeypatch, falsifier_proximity, trail)
    fp = json.loads((trail / "05b-falsifier-proximity.json").read_text(encoding="utf-8"))
    assert fp["stats"]["total"] == 3
    assert {r["ticker"] for r in fp["records"]} == {"KR:003550", "KR:000660", "KR:005930"}

    # 4) Stage 5d thesis_expiry_monitor — 3 position 의 horizon 기반 만료 추적
    _run_no_argv(monkeypatch, thesis_expiry_monitor, trail)
    ex = json.loads((trail / "05d-thesis-expiry.json").read_text(encoding="utf-8"))
    assert ex["stats"]["total"] == 3

    # 5) Stage 5c event_falsifier_linker — event_trigger 1건만, Stage 3 presence → triggered
    (trail / "03-catalyst-events.json").write_text(
        json.dumps({
            "schema": "investment-stage3-catalyst-events-v1",
            "catalysts": [{
                "ticker": "KR:005930",
                "catalyst_type": "treasury_share_cancellation",
                "trigger_class": "a_type",
                "source_citation": f"DART@{DATE}=evt",
            }],
            "d_type_orphans": [],
        }),
        encoding="utf-8",
    )
    assert event_falsifier_linker.main(["--date", DATE, "--trail-dir", str(trail)]) == 0
    ev = json.loads((trail / f"event-trigger-status-{DATE}.json").read_text(encoding="utf-8"))
    assert ev["stats"]["total_event_trigger_positions"] == 1
    rec = ev["records"][0]
    assert rec["ticker"] == "KR:005930"
    assert rec["signal"] == "triggered"  # presence + Stage 3 match
