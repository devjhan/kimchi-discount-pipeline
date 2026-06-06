"""Phase 2.2 — commit_profile drift gate + 버저닝 + 스키마 100% 통과."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from domains.policy.application.commit import commit_profile
from domains.policy.domain.research_result import ResearchOutput
from domains._shared.profile_registry.registry import ProfileRegistry
from infrastructure._common.utils import write_yaml_safely


class _StubAudit:
    def __init__(self) -> None:
        self.records: list[Any] = []

    def record(self, violation: Any) -> None:
        self.records.append(violation)


def _out(ticker: str = "KR:005930", threshold: float = 0.20) -> ResearchOutput:
    return ResearchOutput(
        ticker=ticker,
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


@pytest.mark.unit
def test_research_output_passes_schema_100pct(tmp_path: Path) -> None:
    reg = ProfileRegistry(root=tmp_path)
    audit = _StubAudit()
    commit_profile(_out(), reg, writer=write_yaml_safely, audit_log=audit, drift_threshold=0.5)
    # 재로드 시 ProfileSchemaError 0건 (스키마 100% 통과)
    reloaded = reg.load_version("KR:005930", 1)
    assert reloaded.profile_version == 1
    assert reloaded.required_enrichments == ("nav_discount",)
    assert reloaded.provenance.committed_by == "policy"


@pytest.mark.unit
def test_initial_commit_is_v1(tmp_path: Path) -> None:
    reg = ProfileRegistry(root=tmp_path)
    result = commit_profile(
        _out(), reg, writer=write_yaml_safely, audit_log=_StubAudit(), drift_threshold=0.5
    )
    assert result.version == 1


@pytest.mark.unit
def test_version_increments(tmp_path: Path) -> None:
    reg = ProfileRegistry(root=tmp_path)
    audit = _StubAudit()
    commit_profile(_out(), reg, writer=write_yaml_safely, audit_log=audit, drift_threshold=0.5)
    commit_profile(_out(), reg, writer=write_yaml_safely, audit_log=audit, drift_threshold=0.5)
    third = commit_profile(
        _out(), reg, writer=write_yaml_safely, audit_log=audit, drift_threshold=0.5
    )
    assert third.version == 3
    assert reg.list_versions("KR:005930") == (1, 2, 3)


@pytest.mark.unit
def test_drift_exceeds_threshold_records_audit(tmp_path: Path) -> None:
    reg = ProfileRegistry(root=tmp_path)
    audit = _StubAudit()
    commit_profile(_out(threshold=0.10), reg, writer=write_yaml_safely, audit_log=audit, drift_threshold=0.5)
    result = commit_profile(
        _out(threshold=0.30), reg, writer=write_yaml_safely, audit_log=audit, drift_threshold=0.5
    )
    # max_threshold_delta = |0.30-0.10|/0.10 = 2.0 > 0.5
    assert result.drift.max_threshold_delta == pytest.approx(2.0)
    assert len(audit.records) == 1
    assert audit.records[0].rule_name == "profile_drift"


@pytest.mark.unit
def test_drift_within_threshold_no_audit(tmp_path: Path) -> None:
    reg = ProfileRegistry(root=tmp_path)
    audit = _StubAudit()
    commit_profile(_out(threshold=0.10), reg, writer=write_yaml_safely, audit_log=audit, drift_threshold=0.5)
    commit_profile(_out(threshold=0.11), reg, writer=write_yaml_safely, audit_log=audit, drift_threshold=0.5)
    assert audit.records == []
