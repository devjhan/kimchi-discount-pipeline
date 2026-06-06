"""tests/integration/test_falsifier_proximity_e2e.py — end-to-end CLI smoke."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_falsifier_proximity_cli_dry_run(tmp_path: Path) -> None:
    """CLI 가 --dry-run 으로 정상 종료 + envelope JSON 생성."""
    trail = tmp_path / "trails"
    positions = tmp_path / "positions"
    trail.mkdir()
    positions.mkdir()

    env = os.environ.copy()
    env["TRAIL_TODAY"] = str(trail)
    env["POSITIONS_DIR"] = str(positions)

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "domains.risk_engine.falsifier_proximity",
            "--date",
            "2026-05-09",
            "--dry-run",
            "--trail-dir",
            str(trail),
        ],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 0, f"stderr={proc.stderr}"
    out = trail / "05b-falsifier-proximity.json"
    assert out.exists()
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["schema"] == "investment-stage5b-falsifier-proximity-v1"
    assert payload["stats"]["total"] == 0


def test_falsifier_proximity_e2e_with_position(tmp_path: Path) -> None:
    """실제 thesis.json 1개 → drift-{date}.md 산출 + summary JSON 검증."""
    trail = tmp_path / "trails"
    positions = tmp_path / "positions"
    trail.mkdir()
    positions.mkdir()
    sub = positions / "KR_003550"
    sub.mkdir()
    (sub / "thesis.json").write_text(
        json.dumps(
            {
                "ticker": "KR:003550",
                "name": "LG",
                "entry_date": "2025-09-01",
                "status": "open",
                "thesis": {
                    "time_horizon_months": 12,
                    "falsifier": {"category": "time_cap"},
                },
            }
        )
    )

    env = os.environ.copy()
    env["TRAIL_TODAY"] = str(trail)
    env["POSITIONS_DIR"] = str(positions)

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "domains.risk_engine.falsifier_proximity",
            "--date",
            "2026-05-09",
            "--trail-dir",
            str(trail),
        ],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 0, f"stderr={proc.stderr}"

    # drift md 생성됐는지
    drift_files = list(sub.glob("drift-*.md"))
    assert len(drift_files) == 1
    body = drift_files[0].read_text(encoding="utf-8")
    assert "Falsifier Drift" in body
    assert "time_cap" in body

    # 요약 JSON
    summary = json.loads((trail / "05b-falsifier-proximity.json").read_text())
    assert summary["stats"]["total"] == 1
    assert summary["records"][0]["ticker"] == "KR:003550"
