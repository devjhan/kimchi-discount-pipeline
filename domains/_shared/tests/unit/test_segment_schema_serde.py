"""segment_registry — schema/serde/registry 단위 테스트 (Task 5)."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from domains._shared.segment_registry import serde
from domains._shared.segment_registry.errors import (
    SegmentCycleError,
    SegmentNotFoundError,
    SegmentSchemaError,
)
from domains._shared.segment_registry.registry import (
    NamedProfileRegistry,
    SegmentRegistry,
    ancestor_chain,
    detect_cycle,
)
from domains._shared.segment_registry.schema import (
    SEGMENT_SCHEMA_VERSION,
    MergeSpec,
    PolicyContribution,
    SegmentDefinition,
)


def _seg(seg_id="holdco_large", version=1, **overrides) -> SegmentDefinition:
    kwargs = dict(
        segment_id=seg_id,
        schema_version=SEGMENT_SCHEMA_VERSION,
        segment_version=version,
        selector={"type": "threshold", "attribute": "market_cap_krw", "op": "ge", "threshold": 3e11},
        profile_ref="holdco_floor",
        merge_spec=MergeSpec(),
    )
    kwargs.update(overrides)
    return SegmentDefinition(**kwargs)


@pytest.mark.unit
def test_valid_segment() -> None:
    s = _seg()
    assert s.segment_id == "holdco_large"
    assert s.merge_spec.required_enrichments == "union"


@pytest.mark.unit
def test_bad_merge_op_raises() -> None:
    with pytest.raises(SegmentSchemaError):
        MergeSpec(cutoff_rules="xor")
    with pytest.raises(SegmentSchemaError):
        MergeSpec(required_enrichments="append")


@pytest.mark.unit
def test_selector_without_type_raises() -> None:
    with pytest.raises(SegmentSchemaError):
        _seg(selector={"attribute": "x"})


@pytest.mark.unit
def test_empty_profile_ref_raises() -> None:
    with pytest.raises(SegmentSchemaError):
        _seg(profile_ref="")


@pytest.mark.unit
def test_self_parent_raises() -> None:
    with pytest.raises(SegmentSchemaError):
        _seg(parent="holdco_large")


@pytest.mark.unit
def test_policy_contribution_cutoff_needs_type() -> None:
    with pytest.raises(SegmentSchemaError):
        PolicyContribution(cutoff_rules={"op": "ge"})  # 'type' 누락
    pc = PolicyContribution(required_enrichments=("nav_discount",))
    assert not pc.has_cutoff


@pytest.mark.unit
def test_segment_round_trip() -> None:
    s = _seg(parent="holdco", priority=5)
    assert serde.segment_from_dict(serde.segment_to_dict(s)) == s


@pytest.mark.unit
def test_named_profile_round_trip() -> None:
    pc = PolicyContribution(
        required_enrichments=("nav_discount",),
        cutoff_rules={"type": "threshold", "name": "x", "metric_path": "a", "op": "ge", "threshold": 1.0},
    )
    d = serde.named_profile_to_dict("holdco_floor", 1, pc, description="d")
    assert serde.named_profile_from_dict(d) == pc


@pytest.mark.unit
def test_segment_registry(tmp_path: Path) -> None:
    reg = SegmentRegistry(root=tmp_path)
    assert reg.load_latest("holdco_large") is None
    d = tmp_path / "holdco_large"
    d.mkdir()
    for v in (1, 2):
        (d / f"v{v}.yaml").write_text(
            yaml.safe_dump(serde.segment_to_dict(_seg(version=v)), allow_unicode=True),
            encoding="utf-8",
        )
    assert reg.load_latest("holdco_large").segment_version == 2
    assert reg.list_versions("holdco_large") == (1, 2)
    assert reg.list_segments() == ("holdco_large",)
    assert set(reg.load_all_latest()) == {"holdco_large"}


@pytest.mark.unit
def test_named_profile_registry_missing(tmp_path: Path) -> None:
    reg = NamedProfileRegistry(root=tmp_path)
    assert reg.load_latest("nope") is None
    with pytest.raises(SegmentNotFoundError):
        reg.load_version("nope", 1)


@pytest.mark.unit
def test_ancestor_chain_and_cycle() -> None:
    segs = {
        "root": _seg("root", parent=None),
        "mid": _seg("mid", parent="root"),
        "leaf": _seg("leaf", parent="mid"),
    }
    assert ancestor_chain("leaf", segs) == ["root", "mid", "leaf"]
    detect_cycle(segs)  # no raise

    cyclic = {
        "a": _seg("a", parent="b"),
        "b": _seg("b", parent="a"),
    }
    with pytest.raises(SegmentCycleError):
        detect_cycle(cyclic)
