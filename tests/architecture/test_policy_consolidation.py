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
import yaml  # noqa: E402

import _helpers as h  # noqa: E402

# 정책↔메커니즘 *계약* schema — governance/policy/ 전용. BC-local config 로 새면 안 됨 (ADR-0015).
_POLICY_CONTRACT_SCHEMAS = frozenset(
    {"policy-profile-v1", "segment-def-v1", "segment-concept-v1"}
)


@pytest.mark.arch
def test_all_policy_tiers_under_governance_policy() -> None:
    """profiles(scope buckets) / segments / concepts / strategies 가 governance/policy/ 하위 (ADR-0014)."""
    base = h.REPO_ROOT / "governance" / "policy"
    missing = [
        sub
        for sub in ("profiles", "segments", "concepts", "strategies")
        if not (base / sub).is_dir()
    ]
    assert not missing, f"governance/policy/ 하위 정책 tier 부재: {missing} (ADR-0014 통합)"
    # profiles 는 scope 축(global/segment/ticker)으로 버킷팅된다.
    prof = base / "profiles"
    missing_scopes = [s for s in ("global", "segment", "ticker") if not (prof / s).is_dir()]
    assert not missing_scopes, f"profiles/ scope 버킷 부재: {missing_scopes} (ADR-0014)"


@pytest.mark.arch
def test_global_policy_config_relocated_to_governance() -> None:
    """global(profiles/global) + strategies + hard_guards 가 governance/policy/ 에 거주 (ADR-0014)."""
    base = h.REPO_ROOT / "governance" / "policy"
    assert (base / "strategies").is_dir(), "governance/policy/strategies 부재"
    assert (base / "profiles" / "global").is_dir(), "governance/policy/profiles/global 부재"
    assert (base / "hard_guards.yaml").is_file(), "governance/policy/hard_guards.yaml 부재"


@pytest.mark.arch
def test_legacy_policy_layout_removed() -> None:
    """ADR-0014 restructure — 구 flat-merge 레이아웃(global/ · segment_profiles/) 잔존 금지."""
    base = h.REPO_ROOT / "governance" / "policy"
    assert not (base / "global").exists(), "governance/policy/global 잔존 — ADR-0014 로 해체됨"
    assert not (base / "segment_profiles").exists(), (
        "governance/policy/segment_profiles 잔존 — profiles/segment/ 로 이전됨 (ADR-0014)"
    )


@pytest.mark.arch
def test_no_policy_config_inside_screener_engine() -> None:
    """저장 단일화 — 엔진 BC(domains/screener) 내부에 정책 config 디렉토리 잔존 금지."""
    legacy = h.REPO_ROOT / "domains" / "screener" / "config"
    assert not legacy.exists(), (
        "domains/screener/config 잔존 — global 정책은 governance/policy/global/ 로 "
        "이전되었다 (ADR-0013 decision 1)."
    )


@pytest.mark.arch
def test_no_policy_contract_schema_in_bc_config() -> None:
    """ADR-0015 결합 축 — 정책계약 schema 가 domains/<bc>/config/ 로 새지 않는다.

    cross-cutting 정책계약(policy-profile-v1 / segment-def-v1 / segment-concept-v1)은
    governance/policy/ 전용. BC-local config 는 single-BC 운영 config(plugin manifest +
    그 BC 전용 임계값)만 — 정책계약이 여기 등장하면 배치 기준 위반.
    """
    offenders: list[str] = []
    for cfg_dir in (h.REPO_ROOT / "domains").glob("*/config"):
        for p in cfg_dir.rglob("*.yaml"):
            try:
                raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
            except yaml.YAMLError:
                continue
            if isinstance(raw, dict) and raw.get("schema") in _POLICY_CONTRACT_SCHEMAS:
                offenders.append(f"{h.rel(p)} (schema={raw.get('schema')})")
    assert not offenders, (
        "정책계약 schema 가 BC-local config 로 새어나옴 — governance/policy/ 로 이전 "
        f"(ADR-0015 결합 축): {offenders}"
    )
