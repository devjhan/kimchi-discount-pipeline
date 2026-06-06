"""ProfileRegistry load/commit + serde round-trip 단위 테스트 (Phase 1.2).

writer 는 plan 대로 ``write_output_safely`` 주입 (JSON 직렬화이나 ``yaml.safe_load``
가 JSON superset 으로 재로드 — 왕복 동치). 테스트는 infra import 허용 (registry
패키지 자체의 zero-infra 규율과 무관).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from domains._shared.profile_registry import serde
from domains._shared.profile_registry.registry import ProfileRegistry
from domains._shared.profile_registry.schema import (
    SCHEMA_VERSION,
    EnrichCutoffProfile,
    Provenance,
)
from infrastructure._common.utils import write_output_safely


def _profile(version: int) -> EnrichCutoffProfile:
    return EnrichCutoffProfile(
        ticker="KR:005930",
        schema_version=SCHEMA_VERSION,
        profile_version=version,
        required_enrichments=("nav_discount",),
        cutoff_rules={
            "type": "threshold",
            "name": "nav_floor",
            "metric_path": "enrichments.nav_discount.discount_pct",
            "op": "ge",
            "threshold": 0.20,
        },
        provenance=Provenance(
            committed_at="2026-06-01T16:00:00+09:00",
            committed_by="regression-fixture",
            trigger="manual",
            citations=("DART@2026-05-30T16:00=20260530000123",),
            rationale_ko="테스트",
        ),
        description=f"v{version}",
    )


@pytest.mark.unit
def test_load_latest_picks_highest_version(tmp_path: Path) -> None:
    reg = ProfileRegistry(root=tmp_path)
    for v in (1, 2, 3):
        reg.commit(_profile(v), writer=write_output_safely)
    latest = reg.load_latest("KR:005930")
    assert latest is not None
    assert latest.profile_version == 3
    assert reg.list_versions("KR:005930") == (1, 2, 3)


@pytest.mark.unit
def test_load_missing_ticker_returns_none(tmp_path: Path) -> None:
    reg = ProfileRegistry(root=tmp_path)
    assert reg.load_latest("KR:999999") is None
    assert reg.list_versions("KR:999999") == ()


@pytest.mark.unit
def test_round_trip(tmp_path: Path) -> None:
    p = _profile(2)
    d = serde.to_dict(p)
    assert serde.to_dict(serde.from_dict(d)) == d


@pytest.mark.unit
def test_commit_writes_versioned_file(tmp_path: Path) -> None:
    reg = ProfileRegistry(root=tmp_path)
    p = _profile(1)
    path = reg.commit(p, writer=write_output_safely)
    assert path.exists()
    assert path.name == "v1.yaml"
    assert path.parent.name == "KR_005930"
    reloaded = reg.load_version("KR:005930", 1)
    assert serde.to_dict(reloaded) == serde.to_dict(p)


@pytest.mark.unit
def test_load_version_missing_raises(tmp_path: Path) -> None:
    from domains._shared.profile_registry.errors import ProfileNotFoundError

    reg = ProfileRegistry(root=tmp_path)
    with pytest.raises(ProfileNotFoundError):
        reg.load_version("KR:005930", 7)
