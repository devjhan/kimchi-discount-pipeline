"""domains/_shared/tests/unit/test_brief_validators.py — domains._shared.brief_gate.validators."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from domains._shared.brief_gate.validators import (
    CITATION_RE,
    REQUIRED_FILES,
    validate_stage_inputs,
)

pytestmark = pytest.mark.unit


def _envelope(date: str = "2026-05-09", schema: str = "x-v1") -> dict:
    return {"schema": schema, "generated_at": "2026-05-09T09:00:00+09:00", "date": date}


def _write(p: Path, payload: dict) -> None:
    p.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _all_required_clean(trail: Path) -> None:
    for f in REQUIRED_FILES:
        _write(trail / f, _envelope())


class TestCitationRegex:
    @pytest.mark.parametrize(
        "s, ok",
        [
            ("Yahoo@2026-05-03T16:00=178.50", True),
            ('DART@2026-05-03={"rcept_no":"20260503"}', True),
            ("FRED@2026-05-03=DGS10:4.25", True),
            ("Yahoo 178.50", False),
            ("@2026-05-03=178", False),
            ("Yahoo@=178", False),  # ts 가 비어있음 → \S+ 불일치
            ("Yahoo@2026-05-03=", False),  # value 가 비어있음
        ],
    )
    def test_citation_regex(self, s: str, ok: bool) -> None:
        assert bool(CITATION_RE.match(s)) == ok


class TestValidateStageInputs:
    def test_all_files_missing(self, tmp_path: Path) -> None:
        merged, vio = validate_stage_inputs(tmp_path)
        assert len(vio) == len(REQUIRED_FILES)
        assert all("file not found" in v for v in vio)

    def test_clean_envelope_passes(self, tmp_path: Path) -> None:
        _all_required_clean(tmp_path)
        merged, vio = validate_stage_inputs(tmp_path)
        assert vio == []
        assert merged["00-macro-regime.json"]["date"] == "2026-05-09"

    def test_envelope_missing_schema_field(self, tmp_path: Path) -> None:
        _all_required_clean(tmp_path)
        # 한 파일만 schema 키 제거
        bad = {"generated_at": "x", "date": "2026-05-09"}
        _write(tmp_path / "00-macro-regime.json", bad)
        _, vio = validate_stage_inputs(tmp_path)
        assert any("missing top-level 'schema'" in v for v in vio)

    def test_date_mismatch(self, tmp_path: Path) -> None:
        _all_required_clean(tmp_path)
        _write(tmp_path / "01-universe.json", _envelope(date="2026-05-08"))
        _, vio = validate_stage_inputs(tmp_path)
        assert any("date 불일치" in v for v in vio)

    def test_citation_violation_in_universe_entries(self, tmp_path: Path) -> None:
        _all_required_clean(tmp_path)
        # entry 에 citation 누락
        payload = _envelope() | {
            "entries": [{"ticker": "KR:003550", "name": "LG"}]  # no citation
        }
        _write(tmp_path / "01-universe.json", payload)
        _, vio = validate_stage_inputs(tmp_path)
        assert any("citation 누락 (G7 위반)" in v for v in vio)

    def test_citation_regex_mismatch(self, tmp_path: Path) -> None:
        _all_required_clean(tmp_path)
        payload = _envelope() | {
            "entries": [{"ticker": "KR:003550", "citations": ["bare text not matching"]}]
        }
        _write(tmp_path / "01-universe.json", payload)
        _, vio = validate_stage_inputs(tmp_path)
        assert any("citation G7 정규식 불일치" in v for v in vio)

    def test_sizing_cap_violation(self, tmp_path: Path) -> None:
        _all_required_clean(tmp_path)
        payload = _envelope() | {"cap_violations": ["over kelly cap"]}
        _write(tmp_path / "05-sizing-recommendation.json", payload)
        _, vio = validate_stage_inputs(tmp_path)
        assert any("cap_violations non-empty" in v for v in vio)

    def test_optional_file_missing_no_violation(self, tmp_path: Path) -> None:
        _all_required_clean(tmp_path)
        # optional 파일 (02-quality-lens.json) 미존재 — violation 없음
        _, vio = validate_stage_inputs(tmp_path)
        assert vio == []

    def test_optional_file_broken_json(self, tmp_path: Path) -> None:
        _all_required_clean(tmp_path)
        (tmp_path / "02-quality-lens.json").write_text("not valid json")
        _, vio = validate_stage_inputs(tmp_path)
        assert any("JSON decode fail" in v for v in vio)
