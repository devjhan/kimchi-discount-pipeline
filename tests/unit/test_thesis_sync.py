"""tests/unit/test_thesis_sync.py — Stage 5a thesis.json writer (F-5b / PR3).

projection(schema bridge) 결정론 + verdict/thesis_kind 필터 + 멱등 가드 + G7 citation carry.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from domains._shared.positions_store.store import PositionsStore
from domains.risk_engine.thesis_sync import (
    collect_citations,
    main,
    project_edge_source,
    project_falsifier,
    project_spec,
    project_thesis,
)

DATE = "2026-05-08"  # 금요일 (거래일) — normalize 변환 없음


def _candidate(
    ticker: str = "KR:003550",
    *,
    verdict: str = "accepted",
    kind: str = "new_entry",
    falsifier: dict | None = None,
) -> dict:
    return {
        "ticker": ticker,
        "name": "LG",
        "thesis_kind": kind,
        "verdict": verdict,
        "thesis": {
            "entry_catalyst": {
                "catalyst_id": "DART-20260415-00046127",
                "catalyst_type": "treasury_share_cancellation",
                "trigger_class": "a_type",
            },
            "falsifier": falsifier
            or {
                "categories": ["time_cap"],
                "items": [{"category": "time_cap", "statement": "24개월 내 catalyst 0건 exit", "max_months": 24}],
            },
            "time_horizon_months": 24,
            "edge_source": {"primary": ["C", "D"], "information_edge_claimed": False},
            "asymmetry_score": {
                "downside_floor": {"krw_per_share_or_pct": "-30%", "source_citation": "DART@2026-04-30={NAV:KRW_152000}"},
                "upside_ceiling": {"krw_per_share_or_pct": "+120%", "source_citation": "DART@2026-04-30={NAV:KRW_160000}"},
            },
        },
        "rejection_reason": None,
        "pending_user_questions": [],
        "amendment_diff": None,
    }


def _write_candidates(trail: Path, candidates: list[dict]) -> Path:
    p = trail / "04-thesis-candidates.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps({"schema": "investment-stage4-thesis-candidates-v1", "candidates": candidates}),
        encoding="utf-8",
    )
    return p


# --- pure projection (G6 schema bridge) -----------------------------------

@pytest.mark.unit
def test_project_edge_source_variants() -> None:
    assert project_edge_source({"primary": ["C", "D"]}) == ("C", "D")
    assert project_edge_source(["A"]) == ("A",)
    assert project_edge_source(None) == ()


@pytest.mark.unit
def test_project_spec_metric_trigger_maps_threshold_to_target() -> None:
    spec = project_spec(
        "metric_trigger",
        {"metric": "ROIC_TTM", "threshold": 0.06, "direction": "below", "statement": "ROIC 6% 이하 exit"},
    )
    assert spec["metric"] == "ROIC_TTM"
    assert spec["target_value"] == 0.06  # threshold → target_value
    assert spec["direction"] == "below"


@pytest.mark.unit
def test_project_spec_time_cap_and_event_trigger() -> None:
    tc = project_spec("time_cap", {"max_months": 24, "statement": "x"})
    assert tc == {"max_months": 24, "statement": "x"}
    ev = project_spec(
        "event_trigger",
        {"watch_catalyst_type": "activist_5pct_filing", "direction": "absence", "statement": "행동주의 이탈 시 exit"},
    )
    assert ev["watch_catalyst_type"] == "activist_5pct_filing"
    assert ev["direction"] == "absence"
    assert ev["description"] == "행동주의 이탈 시 exit"


@pytest.mark.unit
def test_project_falsifier_multi_item_warns_and_picks_primary() -> None:
    falsifier = {
        "categories": ["time_cap", "metric_trigger"],
        "items": [
            {"category": "time_cap", "statement": "a", "max_months": 24},
            {"category": "metric_trigger", "metric": "ROIC_TTM", "threshold": 0.06, "direction": "below"},
        ],
    }
    spec, warnings = project_falsifier(falsifier)
    assert spec.category == "time_cap"  # items[0]
    assert len(warnings) == 1 and "다중" in warnings[0]


@pytest.mark.unit
def test_collect_citations_carries_g7() -> None:
    asym = _candidate()["thesis"]["asymmetry_score"]
    cites = collect_citations(asym)
    assert len(cites) == 2
    assert all("DART@" in c for c in cites)


@pytest.mark.unit
def test_project_thesis_full() -> None:
    position, warnings = project_thesis(_candidate(), index=3, date=DATE)
    assert position.ticker == "KR:003550"
    assert position.status == "open"
    assert position.entry_date == DATE
    assert position.entry_price_krw is None
    assert position.time_horizon_months == 24.0
    assert position.edge_source == ("C", "D")
    assert position.falsifier.category == "time_cap"
    assert position.provenance.committed_by == "stage4-derive"
    assert position.provenance.source == "04-thesis-candidates.json#candidates[3]"
    assert len(position.provenance.citations) == 2


# --- main() : filters + idempotency ---------------------------------------

@pytest.mark.unit
def test_writes_thesis_json_for_accepted_new_entry(isolated_workspace) -> None:
    trail = isolated_workspace["trail_today"]
    positions = isolated_workspace["positions_dir"]
    _write_candidates(trail, [_candidate("KR:003550")])

    rc = main(["--date", DATE, "--trail-dir", str(trail)])
    assert rc == 0

    thesis_path = positions / "KR_003550" / "thesis.json"
    assert thesis_path.exists()
    data = json.loads(thesis_path.read_text(encoding="utf-8"))
    assert data["status"] == "open"
    assert data["thesis"]["falsifier"]["category"] == "time_cap"
    assert data["thesis"]["edge_source"] == ["C", "D"]

    # envelope stats
    env = json.loads((trail / "05a-thesis-sync.json").read_text(encoding="utf-8"))
    assert env["stats"]["written"] == 1
    assert env["written"][0]["ticker"] == "KR:003550"


@pytest.mark.unit
def test_skips_amendment_and_rejected(isolated_workspace) -> None:
    trail = isolated_workspace["trail_today"]
    positions = isolated_workspace["positions_dir"]
    _write_candidates(
        trail,
        [
            _candidate("KR:000001", kind="amendment"),
            _candidate("KR:000002", verdict="needs_user_decision"),
            _candidate("KR:000003", verdict="rejected"),
        ],
    )
    rc = main(["--date", DATE, "--trail-dir", str(trail)])
    assert rc == 0
    # 아무 thesis.json 도 안 생김 (전부 user-gated / non-accepted)
    assert not any(positions.glob("*/thesis.json"))
    env = json.loads((trail / "05a-thesis-sync.json").read_text(encoding="utf-8"))
    assert env["stats"]["written"] == 0
    assert env["stats"]["skipped"] == 3


@pytest.mark.unit
def test_idempotent_no_clobber(isolated_workspace) -> None:
    trail = isolated_workspace["trail_today"]
    positions = isolated_workspace["positions_dir"]
    _write_candidates(trail, [_candidate("KR:003550")])

    main(["--date", DATE, "--trail-dir", str(trail)])
    thesis_path = positions / "KR_003550" / "thesis.json"
    first_entry_date = json.loads(thesis_path.read_text())["entry_date"]

    # 다른 date + 별도 trail 로 재실행 (positions 는 공유) — 기존 thesis.json 존재 → clobber 금지
    trail2 = isolated_workspace["root"] / "trail2"
    _write_candidates(trail2, [_candidate("KR:003550")])
    main(["--date", "2026-05-15", "--trail-dir", str(trail2)])

    thesis_files = list((positions / "KR_003550").glob("thesis*.json"))
    assert len(thesis_files) == 1  # .1.json spam 없음
    assert json.loads(thesis_path.read_text())["entry_date"] == first_entry_date  # entry_date 불변

    env = json.loads((trail2 / "05a-thesis-sync.json").read_text(encoding="utf-8"))
    assert env["stats"]["written"] == 0
    assert "clobber 금지" in env["skipped"][0]["reason"]


@pytest.mark.unit
def test_written_thesis_readable_by_store(isolated_workspace) -> None:
    """파생 thesis.json 이 positions_store serde 로 round-trip 가능한지 (reader 호환)."""
    trail = isolated_workspace["trail_today"]
    positions = isolated_workspace["positions_dir"]
    _write_candidates(trail, [_candidate("KR:003550")])
    main(["--date", DATE, "--trail-dir", str(trail)])

    store = PositionsStore(root=positions)
    loaded = store.load_one("KR:003550")
    assert loaded is not None
    assert loaded.falsifier.category == "time_cap"
    assert loaded.provenance.committed_by == "stage4-derive"
    open_positions, warnings = store.load_open()
    assert len(open_positions) == 1 and warnings == []
