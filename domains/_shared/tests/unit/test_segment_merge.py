"""segment_registry.merge — MergeEngine 단위 테스트 (Task 6)."""
from __future__ import annotations

import pytest

from domains._shared.segment_registry.errors import MergeConflictError
from domains._shared.segment_registry.merge import MergeEngine
from domains._shared.segment_registry.schema import (
    SEGMENT_SCHEMA_VERSION,
    MergeSpec,
    PolicyContribution,
    SegmentDefinition,
)


def _seg(seg_id, *, parent=None, priority=0) -> SegmentDefinition:
    return SegmentDefinition(
        segment_id=seg_id,
        schema_version=SEGMENT_SCHEMA_VERSION,
        segment_version=1,
        selector={"type": "threshold", "attribute": "market_cap_krw", "op": "ge", "threshold": 1},
        profile_ref=f"{seg_id}_prof",
        merge_spec=MergeSpec(),
        parent=parent,
        priority=priority,
    )


def _c(re=(), cutoff=None) -> PolicyContribution:
    return PolicyContribution(required_enrichments=tuple(re), cutoff_rules=cutoff or {})


_RULE_A = {"type": "threshold", "name": "a", "metric_path": "x", "op": "ge", "threshold": 1}
_RULE_B = {"type": "threshold", "name": "b", "metric_path": "y", "op": "le", "threshold": 2}


@pytest.mark.unit
def test_required_enrichments_union() -> None:
    out = MergeEngine.merge([
        (_c(re=("a", "b")), MergeSpec()),
        (_c(re=("b", "c")), MergeSpec(required_enrichments="union")),
    ])
    assert out.required_enrichments == ("a", "b", "c")


@pytest.mark.unit
def test_required_enrichments_replace() -> None:
    out = MergeEngine.merge([
        (_c(re=("a", "b")), MergeSpec()),
        (_c(re=("z",)), MergeSpec(required_enrichments="replace")),
    ])
    assert out.required_enrichments == ("z",)


@pytest.mark.unit
def test_cutoff_and_wraps() -> None:
    out = MergeEngine.merge([
        (_c(cutoff=_RULE_A), MergeSpec()),
        (_c(cutoff=_RULE_B), MergeSpec(cutoff_rules="and")),
    ])
    assert out.cutoff_rules["type"] == "and"
    assert out.cutoff_rules["children"] == [_RULE_A, _RULE_B]


@pytest.mark.unit
def test_cutoff_or_wraps() -> None:
    out = MergeEngine.merge([
        (_c(cutoff=_RULE_A), MergeSpec()),
        (_c(cutoff=_RULE_B), MergeSpec(cutoff_rules="or")),
    ])
    assert out.cutoff_rules["type"] == "or"


@pytest.mark.unit
def test_cutoff_replace_child_overrides_parent() -> None:
    out = MergeEngine.merge([
        (_c(cutoff=_RULE_A), MergeSpec()),
        (_c(cutoff=_RULE_B), MergeSpec(cutoff_rules="replace")),
    ])
    assert out.cutoff_rules == _RULE_B


@pytest.mark.unit
def test_cutoff_empty_sides() -> None:
    # 누적 비어있음 → new 그대로; new 비어있음 → 누적 유지
    out = MergeEngine.merge([
        (_c(cutoff={}), MergeSpec()),
        (_c(cutoff=_RULE_A), MergeSpec(cutoff_rules="and")),
        (_c(cutoff={}), MergeSpec(cutoff_rules="and")),
    ])
    assert out.cutoff_rules == _RULE_A


@pytest.mark.unit
def test_order_by_depth_then_priority() -> None:
    segs = {
        "root": _seg("root"),
        "mid": _seg("mid", parent="root", priority=1),
        "leaf": _seg("leaf", parent="mid", priority=5),
    }
    ordered = MergeEngine.order_matched(list(segs.values()), segs)
    assert [s.segment_id for s in ordered] == ["root", "mid", "leaf"]


@pytest.mark.unit
def test_same_depth_priority_breaks_tie() -> None:
    segs = {
        "root": _seg("root"),
        "a": _seg("a", parent="root", priority=1),
        "b": _seg("b", parent="root", priority=2),
    }
    ordered = MergeEngine.order_matched([segs["a"], segs["b"]], segs)
    assert [s.segment_id for s in ordered] == ["a", "b"]  # priority asc → higher last


@pytest.mark.unit
def test_ambiguous_same_depth_priority_raises() -> None:
    segs = {
        "root": _seg("root"),
        "a": _seg("a", parent="root", priority=1),
        "b": _seg("b", parent="root", priority=1),  # 동일 depth+priority
    }
    with pytest.raises(MergeConflictError):
        MergeEngine.order_matched([segs["a"], segs["b"]], segs)
