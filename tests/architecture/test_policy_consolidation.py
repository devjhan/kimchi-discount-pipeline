"""
불변식 — ADR-0013 Q2: 전 정책 tier 가 `governance/policy/` 단일 루트에 거주하고,
global 정책 config 는 엔진 BC(domains/screener) 내부에 잔존하지 않는다 (저장 단일화).

선언적 정책의 위치를 fitness 로 고정해 회귀(엔진 내부로 config 가 다시 새는 것)를 차단한다.
cutoff *평가* 는 여전히 screener RuleFactory 가 소유하지만(decision 3), *저장* 은
governance/policy/ 로 통일된다.
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import pytest  # noqa: E402

import _helpers as h  # noqa: E402


@pytest.mark.arch
def test_all_policy_tiers_under_governance_policy() -> None:
    """per-ticker / segment / concept / segment_profile / global 이 governance/policy/ 하위."""
    base = h.REPO_ROOT / "governance" / "policy"
    missing = [
        sub
        for sub in ("profiles", "segments", "concepts", "segment_profiles", "global")
        if not (base / sub).is_dir()
    ]
    assert not missing, f"governance/policy/ 하위 정책 tier 부재: {missing} (ADR-0013 통합)"


@pytest.mark.arch
def test_global_policy_config_relocated_to_governance() -> None:
    """global(strategy/profile/hard_guards) 이 governance/policy/global/ 에 거주."""
    g = h.REPO_ROOT / "governance" / "policy" / "global"
    assert (g / "strategies").is_dir(), "governance/policy/global/strategies 부재"
    assert (g / "profiles").is_dir(), "governance/policy/global/profiles 부재"
    assert (g / "hard_guards.yaml").is_file(), "governance/policy/global/hard_guards.yaml 부재"


@pytest.mark.arch
def test_no_policy_config_inside_screener_engine() -> None:
    """저장 단일화 — 엔진 BC(domains/screener) 내부에 정책 config 디렉토리 잔존 금지."""
    legacy = h.REPO_ROOT / "domains" / "screener" / "config"
    assert not legacy.exists(), (
        "domains/screener/config 잔존 — global 정책은 governance/policy/global/ 로 "
        "이전되었다 (ADR-0013 decision 1)."
    )
