"""applications/bootstrap_profiles — cold-start 러너 단위테스트 (Task 2, TDD).

러너는 commit/drift/version 산술을 재구현하지 않고 domains.policy.main 의 결정론
진입점(intake / --commit-draft)을 재사용한다 (F-10). 본 테스트는 그 오케스트레이션
(배치 intake / draft 부재 graceful / draft commit 위임 / malformed reject / resume 멱등)
을 fixture(네트워크 0)로 고정한다.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from applications import bootstrap_profiles as bp
from domains._shared.profile_registry.registry import ProfileRegistry
from domains.policy import _boundary as policy_boundary

DATE = "2026-06-15"


def _draft(ticker: str = "KR:003550", threshold: float = 0.5) -> dict:
    """strict validator 통과하는 정상 draft (whitelist metric_path/op/type)."""
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
        "rationale_ko": "테스트 draft",
    }


def _write_draft(tmp_path: Path, ticker: str, payload: dict, date: str = DATE) -> Path:
    tdir = tmp_path / "drafts" / ticker.replace(":", "_")
    tdir.mkdir(parents=True, exist_ok=True)
    p = tdir / f"_profile-draft-{date}.json"
    p.write_text(json.dumps(payload), encoding="utf-8")
    return p


@pytest.fixture
def iso(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """profiles_root / drafts_dir 를 tmp 로 격리 (policy.main 과 공유 게이트)."""
    monkeypatch.setattr(policy_boundary, "profiles_root", lambda: tmp_path / "profiles")
    monkeypatch.setattr(policy_boundary, "drafts_dir", lambda: tmp_path / "drafts")
    return tmp_path


@pytest.mark.unit
def test_intake_batch_creates_intake_files(iso: Path) -> None:
    rc = bp.main(["--tickers", "KR:003550", "KR:005930", "--phase", "intake", "--date", DATE])
    assert rc == 0
    for tdir in ("KR_003550", "KR_005930"):
        assert (iso / "drafts" / tdir / f"_intake-{DATE}.json").exists()


@pytest.mark.unit
def test_commit_phase_waits_when_no_draft(iso: Path) -> None:
    """draft 미존재 → waiting (비-에러, exit 0), profile 미생성 (Default No-Action)."""
    rc = bp.main(["--tickers", "KR:003550", "--phase", "commit", "--date", DATE])
    assert rc == 0
    assert ProfileRegistry(root=iso / "profiles").load_latest("KR:003550") is None


@pytest.mark.unit
def test_commit_phase_commits_present_draft(iso: Path) -> None:
    """draft 존재 → commit 위임 → v1 + draft archive(.committed)."""
    draft = _write_draft(iso, "KR:003550", _draft())
    rc = bp.main(["--tickers", "KR:003550", "--phase", "commit", "--date", DATE])
    assert rc == 0
    p = ProfileRegistry(root=iso / "profiles").load_latest("KR:003550")
    assert p is not None and p.profile_version == 1
    assert not draft.exists()  # active draft archived
    assert draft.with_name(draft.stem + ".committed.json").exists()


@pytest.mark.unit
def test_commit_phase_rejects_malformed_draft(iso: Path) -> None:
    """ticker 없는 draft → malformed → exit 2, profile 미생성, draft 미-archive."""
    draft = _write_draft(iso, "KR:003550", {"required_enrichments": []})
    rc = bp.main(["--tickers", "KR:003550", "--phase", "commit", "--date", DATE])
    assert rc == 2
    assert ProfileRegistry(root=iso / "profiles").load_latest("KR:003550") is None
    assert draft.exists()  # malformed → 보존(보고)


@pytest.mark.unit
def test_resume_idempotent_after_commit(iso: Path) -> None:
    """commit 후 재실행 → archived draft 는 'done', 재-commit 안 함 (v1 유지)."""
    _write_draft(iso, "KR:003550", _draft())
    rc1 = bp.main(["--tickers", "KR:003550", "KR:005930", "--phase", "commit", "--date", DATE])
    assert rc1 == 0  # 003550 committed, 005930 waiting
    reg = ProfileRegistry(root=iso / "profiles")
    assert reg.load_latest("KR:003550").profile_version == 1
    rc2 = bp.main(["--tickers", "KR:003550", "KR:005930", "--phase", "commit", "--date", DATE])
    assert rc2 == 0
    assert reg.load_latest("KR:003550").profile_version == 1  # NOT bumped (idempotent)


@pytest.mark.unit
def test_invalid_ticker_reported_exit2(iso: Path) -> None:
    """KR:NNNNNN 형식 위반 → 경고 + exit 2 (actionable 신호)."""
    rc = bp.main(["--tickers", "003550", "--phase", "intake", "--date", DATE])
    assert rc == 2


@pytest.mark.unit
def test_tickers_file_loaded(iso: Path, tmp_path: Path) -> None:
    """--tickers-file 로드 (# 주석/빈줄 skip)."""
    f = tmp_path / "watchlist.txt"
    f.write_text("# 코멘트\nKR:003550\n\nKR:005930\n", encoding="utf-8")
    rc = bp.main(["--tickers-file", str(f), "--phase", "intake", "--date", DATE])
    assert rc == 0
    assert (iso / "drafts" / "KR_003550" / f"_intake-{DATE}.json").exists()
    assert (iso / "drafts" / "KR_005930" / f"_intake-{DATE}.json").exists()
