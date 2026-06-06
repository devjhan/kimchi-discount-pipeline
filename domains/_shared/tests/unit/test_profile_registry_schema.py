"""EnrichCutoffProfile __post_init__ shape 검증 단위 테스트 (Phase 1.1)."""
from __future__ import annotations

import pytest

from domains._shared.profile_registry.errors import ProfileSchemaError
from domains._shared.profile_registry.schema import (
    SCHEMA_VERSION,
    EnrichCutoffProfile,
    Provenance,
)


def _valid_kwargs(**overrides):
    kwargs = dict(
        ticker="KR:005930",
        schema_version=SCHEMA_VERSION,
        profile_version=1,
        required_enrichments=("nav_discount",),
        cutoff_rules={"type": "and", "name": "c", "children": []},
        provenance=Provenance(
            committed_at="2026-06-01T16:00:00+09:00",
            committed_by="policy",
            trigger="manual",
        ),
        description="샘플",
    )
    kwargs.update(overrides)
    return kwargs


@pytest.mark.unit
def test_valid_profile_constructs() -> None:
    p = EnrichCutoffProfile(**_valid_kwargs())
    assert p.ticker == "KR:005930"
    assert p.profile_version == 1
    assert p.required_enrichments == ("nav_discount",)


@pytest.mark.unit
def test_invalid_ticker_raises() -> None:
    with pytest.raises(ProfileSchemaError):
        EnrichCutoffProfile(**_valid_kwargs(ticker="005930"))  # 콜론 없음


@pytest.mark.unit
def test_version_zero_raises() -> None:
    with pytest.raises(ProfileSchemaError):
        EnrichCutoffProfile(**_valid_kwargs(profile_version=0))


@pytest.mark.unit
def test_cutoff_rules_without_type_raises() -> None:
    with pytest.raises(ProfileSchemaError):
        EnrichCutoffProfile(**_valid_kwargs(cutoff_rules={}))


@pytest.mark.unit
def test_schema_version_mismatch_raises() -> None:
    with pytest.raises(ProfileSchemaError):
        EnrichCutoffProfile(**_valid_kwargs(schema_version="enrich-cutoff-profile-v999"))


@pytest.mark.unit
def test_empty_required_enrichments_allowed() -> None:
    """보강 불요 종목 — 빈 tuple 허용 (에지 케이스)."""
    p = EnrichCutoffProfile(**_valid_kwargs(required_enrichments=()))
    assert p.required_enrichments == ()
