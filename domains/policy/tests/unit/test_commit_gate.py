"""commit_gate 도메인 룰 직접 단위테스트 (F-4 part1).

버전 발급 / drift 차단판정 / provenance 조립을 application 경유 없이 검증.
차단/경고 의미는 ``DRIFT_BLOCKS_COMMIT`` 단일 플래그가 결정 (현재 advisory=False).
"""
from __future__ import annotations

import pytest

from domains.policy.domain import commit_gate
from domains.policy.domain.commit_gate import (
    assemble_profile,
    decide_commit,
    next_version,
    rule_on_drift,
)
from domains.policy.domain.research_result import ResearchOutput
from domains._shared.profile_registry.schema import (
    SCHEMA_VERSION,
    EnrichCutoffProfile,
    Provenance,
)


def _out(*, threshold: float = 0.10) -> ResearchOutput:
    return ResearchOutput(
        ticker="KR:005930",
        required_enrichments=("nav_discount",),
        cutoff_rules={
            "type": "threshold",
            "name": "nav_floor",
            "metric_path": "enrichments.nav_discount.discount_pct",
            "op": "ge",
            "threshold": threshold,
        },
        citations=("DART@2026-05-30T16:00=20260530000123",),
        rationale_ko="테스트 프로파일",
    )


def _profile(*, version: int = 1, threshold: float = 0.10) -> EnrichCutoffProfile:
    return EnrichCutoffProfile(
        ticker="KR:005930",
        schema_version=SCHEMA_VERSION,
        profile_version=version,
        required_enrichments=("nav_discount",),
        cutoff_rules={"type": "threshold", "name": "nav_floor", "threshold": threshold},
        provenance=Provenance(
            committed_at="2026-06-02T16:00:00+09:00", committed_by="policy", trigger="manual"
        ),
    )


@pytest.mark.unit
def test_next_version_initial_is_1() -> None:
    assert next_version(None) == 1


@pytest.mark.unit
def test_next_version_increments() -> None:
    assert next_version(_profile(version=3)) == 4


@pytest.mark.unit
def test_rule_on_drift_initial_never_exceeds() -> None:
    ruling = rule_on_drift(None, _out(), drift_threshold=0.5)
    assert ruling.exceeds_threshold is False
    assert ruling.blocks_commit is False
    assert ruling.drift.max_threshold_delta == 0.0


@pytest.mark.unit
def test_rule_on_drift_exceeds_threshold() -> None:
    prev = _profile(threshold=0.10)
    ruling = rule_on_drift(prev, _out(threshold=0.30), drift_threshold=0.5)
    # |0.30-0.10|/0.10 = 2.0 > 0.5
    assert ruling.exceeds_threshold is True


@pytest.mark.unit
def test_rule_on_drift_within_threshold() -> None:
    prev = _profile(threshold=0.10)
    ruling = rule_on_drift(prev, _out(threshold=0.11), drift_threshold=0.5)
    assert ruling.exceeds_threshold is False


@pytest.mark.unit
def test_blocks_commit_false_under_advisory_default() -> None:
    # Wave 1: advisory — 초과해도 차단 안 함.
    assert commit_gate.DRIFT_BLOCKS_COMMIT is False
    prev = _profile(threshold=0.10)
    ruling = rule_on_drift(prev, _out(threshold=0.30), drift_threshold=0.5)
    assert ruling.exceeds_threshold is True
    assert ruling.blocks_commit is False


@pytest.mark.unit
def test_assemble_profile_provenance_fields() -> None:
    profile = assemble_profile(
        _out(), version=2, committed_at="2026-06-03T09:00:00+09:00", trigger="filing:rcept=1"
    )
    assert profile.profile_version == 2
    assert profile.schema_version == SCHEMA_VERSION
    assert profile.provenance.committed_by == "policy"
    assert profile.provenance.trigger == "filing:rcept=1"
    assert profile.provenance.citations == ("DART@2026-05-30T16:00=20260530000123",)
    assert profile.description == "테스트 프로파일"


@pytest.mark.unit
def test_decide_commit_bundles_version_ruling_profile() -> None:
    prev = _profile(threshold=0.10)
    decision = decide_commit(
        prev,
        _out(threshold=0.30),
        drift_threshold=0.5,
        committed_at="2026-06-03T09:00:00+09:00",
        trigger="manual",
    )
    assert decision.version == 2
    assert decision.ruling.exceeds_threshold is True
    assert decision.profile.profile_version == 2
