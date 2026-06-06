"""positions_store schema/serde/store 단위 테스트 (F-5b / PR1).

writer 는 plan 대로 ``write_output_safely`` 주입 (테스트는 infra import 허용 —
positions_store 패키지 자체의 zero-infra 규율과 무관).

byte-parity 핵심: ``load_open_raw`` 가 risk_engine 3 로더의 graceful skip 거동
(corrupt JSON warning 포맷 / status!=open skip / category 필터)을 그대로 보존하는지.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from domains._shared.positions_store import serde
from domains._shared.positions_store.errors import PositionSchemaError
from domains._shared.positions_store.schema import (
    SCHEMA_VERSION,
    FalsifierSpec,
    PositionThesis,
    ThesisProvenance,
)
from domains._shared.positions_store.store import PositionsStore
from infrastructure._common.utils import write_output_safely


def _thesis(ticker: str = "KR:003550", *, status: str = "open", category: str = "time_cap") -> PositionThesis:
    return PositionThesis(
        ticker=ticker,
        name="LG",
        falsifier=FalsifierSpec(category=category, spec={"description": "x"}),
        entry_date="2026-01-15",
        time_horizon_months=18.0,
        edge_source=("C", "D"),
        entry_price_krw=84000.0,
        status=status,
        entry_catalyst="자사주 소각",
        asymmetry_score={"downside_floor": -0.2, "upside_ceiling": 0.8},
        provenance=ThesisProvenance(
            committed_at="2026-06-04T16:00:00+09:00",
            committed_by="regression-fixture",
            source="manual",
            citations=("KIS@2026-06-04T16:00=84000",),
            rationale_ko="테스트",
        ),
    )


def _write_thesis_dict(root: Path, ticker_dir: str, data: dict) -> Path:
    sub = root / ticker_dir
    sub.mkdir(parents=True, exist_ok=True)
    p = sub / "thesis.json"
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return p


# --- schema __post_init__ -------------------------------------------------

@pytest.mark.unit
def test_valid_thesis_constructs() -> None:
    t = _thesis()
    assert t.ticker == "KR:003550"
    assert t.falsifier.category == "time_cap"


@pytest.mark.unit
def test_malformed_ticker_raises() -> None:
    with pytest.raises(PositionSchemaError):
        _thesis(ticker="003550")  # 콜론 없음


@pytest.mark.unit
def test_unknown_falsifier_category_raises() -> None:
    with pytest.raises(PositionSchemaError):
        FalsifierSpec(category="vibes_trigger")


@pytest.mark.unit
def test_tolerates_missing_horizon_and_date() -> None:
    """monitor 가 unmeasurable 로 처리하므로 누락 horizon/date 는 raise 안 함."""
    t = PositionThesis(ticker="KR:000660", falsifier=FalsifierSpec(category="event_trigger"))
    assert t.time_horizon_months is None
    assert t.entry_date == ""
    assert t.entry_price_krw is None


# --- serde round-trip / schema gate ---------------------------------------

@pytest.mark.unit
def test_round_trip() -> None:
    d = serde.to_dict(_thesis())
    assert serde.to_dict(serde.from_dict(d)) == d


@pytest.mark.unit
def test_on_disk_shape_matches_readme() -> None:
    """README §3 의 nested thesis.{falsifier,...} shape 를 monitor 가 .get() 으로 읽는다."""
    d = serde.to_dict(_thesis())
    assert d["schema"] == SCHEMA_VERSION
    assert d["thesis"]["falsifier"]["category"] == "time_cap"
    assert d["thesis"]["time_horizon_months"] == 18.0
    assert d["thesis"]["edge_source"] == ["C", "D"]
    assert "_provenance" in d


@pytest.mark.unit
def test_schemaless_dict_accepted() -> None:
    """레거시/수기 thesis.json (schema 키 없음) → 'v1 unversioned' 수용."""
    raw = {
        "ticker": "KR:003550",
        "status": "open",
        "thesis": {"falsifier": {"category": "time_cap", "spec": {}}, "time_horizon_months": 12},
    }
    t = serde.from_dict(raw)
    assert t.ticker == "KR:003550"
    assert t.time_horizon_months == 12.0


@pytest.mark.unit
def test_schema_mismatch_rejected() -> None:
    raw = serde.to_dict(_thesis())
    raw["schema"] = "positions-thesis-v999"
    with pytest.raises(PositionSchemaError):
        serde.from_dict(raw)


@pytest.mark.unit
def test_from_dict_bad_category_raises() -> None:
    raw = serde.to_dict(_thesis())
    raw["thesis"]["falsifier"]["category"] = "nope"
    with pytest.raises(PositionSchemaError):
        serde.from_dict(raw)


# --- load_open_raw (byte-parity with 3 readers) ---------------------------

@pytest.mark.unit
def test_load_open_raw_missing_dir_empty(tmp_path: Path) -> None:
    store = PositionsStore(root=tmp_path / "nope")
    assert store.load_open_raw() == ([], [])


@pytest.mark.unit
def test_load_open_raw_filters_status(tmp_path: Path) -> None:
    _write_thesis_dict(tmp_path, "KR_001", {"ticker": "KR:001", "status": "open", "thesis": {}})
    _write_thesis_dict(tmp_path, "KR_002", {"ticker": "KR:002", "status": "closed", "thesis": {}})
    _write_thesis_dict(tmp_path, "KR_003", {"ticker": "KR:003", "thesis": {}})  # status 누락 → open 취급
    store = PositionsStore(root=tmp_path)
    out, warnings = store.load_open_raw()
    assert {d["ticker"] for d in out} == {"KR:001", "KR:003"}
    assert warnings == []


@pytest.mark.unit
def test_load_open_raw_category_filter(tmp_path: Path) -> None:
    _write_thesis_dict(
        tmp_path, "KR_001",
        {"ticker": "KR:001", "status": "open", "thesis": {"falsifier": {"category": "event_trigger"}}},
    )
    _write_thesis_dict(
        tmp_path, "KR_002",
        {"ticker": "KR:002", "status": "open", "thesis": {"falsifier": {"category": "time_cap"}}},
    )
    store = PositionsStore(root=tmp_path)
    out, _ = store.load_open_raw(category="event_trigger")
    assert [d["ticker"] for d in out] == ["KR:001"]


@pytest.mark.unit
def test_load_open_raw_corrupt_skip_with_warning(tmp_path: Path) -> None:
    sub = tmp_path / "KR_001"
    sub.mkdir(parents=True)
    (sub / "thesis.json").write_text("{ not json", encoding="utf-8")
    store = PositionsStore(root=tmp_path)
    out, warnings = store.load_open_raw()
    assert out == []
    assert len(warnings) == 1
    assert warnings[0].startswith("thesis.json parse fail:")  # 리더와 동일 포맷


@pytest.mark.unit
def test_load_open_raw_skips_non_dir_and_missing_thesis(tmp_path: Path) -> None:
    (tmp_path / "stray.json").write_text("{}", encoding="utf-8")  # 비-디렉토리
    (tmp_path / "KR_empty").mkdir()  # thesis.json 부재
    store = PositionsStore(root=tmp_path)
    assert store.load_open_raw() == ([], [])


# --- load_open (typed) ----------------------------------------------------

@pytest.mark.unit
def test_load_open_typed_graceful_schema_skip(tmp_path: Path) -> None:
    """손상 schema 는 raise 대신 warning + skip (raw 로더 tolerance 와 일치)."""
    _write_thesis_dict(
        tmp_path, "KR_ok",
        serde.to_dict(_thesis("KR:003550")),
    )
    _write_thesis_dict(
        tmp_path, "KR_bad",
        {"ticker": "KR:000660", "status": "open", "thesis": {"falsifier": {"category": "bogus"}}},
    )
    store = PositionsStore(root=tmp_path)
    out, warnings = store.load_open()
    assert [t.ticker for t in out] == ["KR:003550"]
    assert any("schema invalid" in w for w in warnings)


# --- commit / path --------------------------------------------------------

@pytest.mark.unit
def test_commit_writes_thesis_json(tmp_path: Path) -> None:
    store = PositionsStore(root=tmp_path)
    path = store.commit(_thesis("KR:003550"), writer=write_output_safely)
    assert path.exists()
    assert path.name == "thesis.json"
    assert path.parent.name == "KR_003550"  # 콜론 sanitize
    reloaded = store.load_one("KR:003550")
    assert reloaded is not None
    assert serde.to_dict(reloaded) == serde.to_dict(_thesis("KR:003550"))


@pytest.mark.unit
def test_has_open_thesis(tmp_path: Path) -> None:
    store = PositionsStore(root=tmp_path)
    assert store.has_open_thesis("KR:003550") is False
    store.commit(_thesis("KR:003550", status="open"), writer=write_output_safely)
    assert store.has_open_thesis("KR:003550") is True
    # closed → has_open False
    _write_thesis_dict(tmp_path, "KR_000660", {"ticker": "KR:000660", "status": "closed"})
    assert store.has_open_thesis("KR:000660") is False


@pytest.mark.unit
def test_load_one_missing_returns_none(tmp_path: Path) -> None:
    store = PositionsStore(root=tmp_path)
    assert store.load_one("KR:999999") is None
