"""Phase 6a — policy main 3-phase wiring: --commit-draft (phase 3) + _intake (phase 1).

스킬(investment-policy-profiler)이 만든 profile-draft 를 결정론 commit 하는 경로 +
intake 산출(현 profile 동봉) 검증. 스킬 자체는 commit 안 함 (F-10 불변식) — 본 테스트는
그 결정론 절반(intake/commit)을 고정한다.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from domains.policy import _boundary
from domains.policy import main as policy_main
from domains._shared.profile_registry.registry import ProfileRegistry


def _draft_payload(ticker: str = "KR:005930", threshold: float = 0.20) -> dict:
    return {
        "ticker": ticker,
        "required_enrichments": ["nav_discount"],
        "cutoff_rules": {
            "type": "threshold",
            "name": "nav_floor",
            "metric_path": "enrichments.nav_discount.discount_pct",
            "op": "ge",
            "threshold": threshold,
        },
        "citations": ["DART@2026-05-30T16:00=20260530000123"],
        "rationale_ko": "스킬 산출 draft",
    }


@pytest.fixture
def iso(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """profiles_root / drafts_dir 를 tmp 로 격리."""
    monkeypatch.setattr(_boundary, "profiles_root", lambda: tmp_path / "profiles")
    monkeypatch.setattr(_boundary, "drafts_dir", lambda: tmp_path / "drafts")
    return tmp_path


@pytest.mark.unit
def test_commit_draft_commits_profile(iso: Path) -> None:
    """--commit-draft <json> → 결정론 commit (v1, registry 재로드 가능)."""
    draft = iso / "draft.json"
    draft.write_text(json.dumps(_draft_payload()), encoding="utf-8")
    rc = policy_main.main(["--commit-draft", str(draft), "--date", "2026-05-15"])
    assert rc == 0
    p = ProfileRegistry(root=iso / "profiles").load_latest("KR:005930")
    assert p is not None
    assert p.profile_version == 1
    assert p.required_enrichments == ("nav_discount",)
    assert p.provenance.committed_by == "policy"


@pytest.mark.unit
def test_commit_draft_accepts_envelope_payload(iso: Path) -> None:
    """draft 가 envelope({payload:...}) 형태여도 commit."""
    draft = iso / "draft.json"
    draft.write_text(json.dumps({"payload": _draft_payload()}), encoding="utf-8")
    rc = policy_main.main(["--commit-draft", str(draft), "--date", "2026-05-15"])
    assert rc == 0
    assert ProfileRegistry(root=iso / "profiles").load_latest("KR:005930") is not None


@pytest.mark.unit
def test_commit_draft_missing_file_exit2(iso: Path) -> None:
    """존재하지 않는 draft → exit 2 (비-graceful, audit 신호)."""
    rc = policy_main.main(["--commit-draft", str(iso / "nope.json"), "--date", "2026-05-15"])
    assert rc == 2


@pytest.mark.unit
def test_commit_draft_bad_schema_exit2(iso: Path) -> None:
    """ticker 없는 draft → exit 2."""
    draft = iso / "bad.json"
    draft.write_text(json.dumps({"required_enrichments": []}), encoding="utf-8")
    rc = policy_main.main(["--commit-draft", str(draft), "--date", "2026-05-15"])
    assert rc == 2


@pytest.mark.unit
def test_intake_emits_intake_artifact(iso: Path) -> None:
    """--ticker --dry-run → _intake-{date}.json (trigger + current_profile=None)."""
    rc = policy_main.main(
        ["--ticker", "KR:005930", "--trigger", "filing:rcept_no=1", "--dry-run", "--date", "2026-05-15"]
    )
    assert rc == 0
    intake_path = iso / "drafts" / "KR_005930" / "_intake-2026-05-15.json"
    assert intake_path.exists()
    data = json.loads(intake_path.read_text(encoding="utf-8"))
    payload = data.get("payload", data)
    assert payload["trigger"]["ticker"] == "KR:005930"
    assert payload["current_profile"] is None  # tmp profiles 비어있음
    # evidence_dir_hint 는 telemetry/external_signals 로 이전 (config/signals 아님).
    assert payload["evidence_dir_hint"] == "telemetry/external_signals/KR_005930/"
