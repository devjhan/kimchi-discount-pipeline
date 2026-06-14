"""
tests/conftest.py — pytest fixtures.

핵심 fixture:
    isolated_workspace: tmp_path 기반 가짜 $TRAIL_TODAY / $AUDIT_DIR /
        $POSITIONS_DIR 환경변수 monkeypatch. domains 코드가 utils path helper
        (trail_dir / audit_dir / positions_dir 등) 로 path 해소할 때 — helper 가
        env var 우선이라 — 가짜 디렉토리를 보도록.

    sample_thesis: stage 5b falsifier_proximity 의 입력 fixture.

    sample_state: stat_tests 의 quarterly_returns / evaluate_self_disable_trigger
        입력 fixture (4-tier shadow portfolio state).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

# tests/ 가 패키지 import 경로에 들어가도록 (pyproject.toml + setuptools 미실행 시 안전)
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


@pytest.fixture
def isolated_workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """
    tmp_path 안에 alias dir 생성 + env var monkeypatch.

    2026-06-02 operations/ 재편: audit→telemetry/audit, positions→telemetry/positions,
    external_signals→config/signals 로 helper default 경로가 이동했으나 env-var 이름은
    유지되어 (테스트 격리 seam) tmp 재지정은 동일하게 동작한다. per-ticker ingest 증거는
    telemetry/external_signals (EXTERNAL_SIGNAL_INTAKE_DIR) 로 분리 — breadth(config/signals)
    와 다른 helper(external_signal_intake_dir).

    Returns:
        dict with keys: trail_today, audit_dir, positions_dir, external_signals_dir,
                        external_signal_intake_dir, user_context_dir, root.
    """
    trail = tmp_path / "operations" / "2026-05-09" / ".trails"
    audit = tmp_path / "telemetry" / "audit"
    positions = tmp_path / "telemetry" / "positions"
    external = tmp_path / "config" / "signals"
    external_intake = tmp_path / "telemetry" / "external_signals"
    user_ctx = tmp_path / "config" / "user"
    for d in (trail, audit, positions, external, external_intake, user_ctx):
        d.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("TRAIL_TODAY", str(trail))
    monkeypatch.setenv("AUDIT_DIR", str(audit))
    monkeypatch.setenv("POSITIONS_DIR", str(positions))
    monkeypatch.setenv("EXTERNAL_SIGNALS_DIR", str(external))
    monkeypatch.setenv("EXTERNAL_SIGNAL_INTAKE_DIR", str(external_intake))
    # USER_CONTEXT_DIR 은 utils 가 직접 참조하지 않음 (user_context 는 config/user
    # 하드코딩 — env override 불가). dict-key 호환 위해 set 만 유지.
    monkeypatch.setenv("USER_CONTEXT_DIR", str(user_ctx))

    return {
        "root": tmp_path,
        "trail_today": trail,
        "audit_dir": audit,
        "positions_dir": positions,
        "external_signals_dir": external,
        "external_signal_intake_dir": external_intake,
        "user_context_dir": user_ctx,
    }


@pytest.fixture
def sample_thesis() -> dict[str, Any]:
    return {
        "ticker": "KR:003550",
        "name": "LG",
        "entry_date": "2026-01-15",
        "entry_price_krw": 84000,
        "status": "open",
        "thesis": {
            "entry_catalyst": "자사주 소각 발표",
            "falsifier": {
                "category": "time_cap",
                "spec": {},
            },
            "time_horizon_months": 18,
            "edge_source": ["C", "D"],
            "asymmetry_score": {
                "downside_floor": {"krw_per_share_or_pct": "-25%"},
                "upside_ceiling": {"krw_per_share_or_pct": "+80%"},
            },
        },
    }


@pytest.fixture
def sample_state() -> dict[str, Any]:
    """4-tier shadow portfolio state. tier_2 가 4분기 연속 tier_1 보다 음수."""
    return {
        "schema": "investment-shadow-portfolio-state-v1",
        "init_date": "2025-04-01",
        "tiers": {
            "tier_0_passive_index": {"quarterly_history": [0.020, 0.025, 0.030, 0.022]},
            "tier_1_mechanical": {"quarterly_history": [0.034, 0.045, 0.038, 0.041]},
            "tier_2_llm_filtered": {"quarterly_history": [0.018, 0.022, 0.020, 0.025]},
            "tier_3_random": {"quarterly_history": [0.005, 0.012, -0.003, 0.008]},
        },
    }


@pytest.fixture
def write_json(tmp_path: Path):
    """헬퍼: dict 를 path 에 JSON 으로 write 후 path 반환."""
    def _write(p: Path, payload: dict[str, Any]) -> Path:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return p

    return _write
