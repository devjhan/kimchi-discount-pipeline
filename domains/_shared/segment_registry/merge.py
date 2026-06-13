"""MergeEngine — 명시적 per-field 합성 + 계층 정렬 (6-a).

합성 순서: general → specific. fold 의 각 step 은 *그 step 의 merge_spec* 으로 누적값에
얹힌다. 연산자는 선언적이며 암묵 동작이 없다:

- required_enrichments: ``union`` (누적 ∪ 신규, 순서보존 dedup) | ``replace`` (신규로 치환)
- cutoff_rules: ``and`` / ``or`` (누적·신규를 해당 합성노드로 wrap) | ``replace``

계층 정렬: 매칭된 segment 들을 (depth asc, priority asc) 로 정렬해 *덜 구체적인 것 먼저*
적용하고 더 구체적/고priority 가 나중에 (replace 시 우선). depth = parent 체인 길이.
**동일 (depth, priority) 의 다중 매칭은 순서 모호 → MergeConflictError** (명시적 해소
강제, 암묵 tie-break 금지).
"""
from __future__ import annotations

from typing import Any, Mapping

from domains._shared.segment_registry.errors import MergeConflictError
from domains._shared.segment_registry.registry import ancestor_chain
from domains._shared.segment_registry.schema import (
    MergeSpec,
    PolicyContribution,
    SegmentDefinition,
)


def _union_preserve(acc: tuple[str, ...], new: tuple[str, ...]) -> tuple[str, ...]:
    seen: set[str] = set()
    out: list[str] = []
    for x in (*acc, *new):
        if x and x not in seen:
            seen.add(x)
            out.append(x)
    return tuple(out)


def _combine_cutoff(
    acc: Mapping[str, Any], new: Mapping[str, Any], op: str
) -> Mapping[str, Any]:
    """cutoff_rules 합성. 빈 쪽은 무시; 둘 다 있으면 op(and/or) 노드로 wrap; replace 면 new."""
    if op == "replace":
        return dict(new) if new else dict(acc)
    if not acc:
        return dict(new)
    if not new:
        return dict(acc)
    return {"type": op, "name": f"segment_merge_{op}", "children": [dict(acc), dict(new)]}


class MergeEngine:
    """PolicyContribution fold + segment 계층 정렬."""

    @staticmethod
    def order_matched(
        matched: list[SegmentDefinition], segments: Mapping[str, SegmentDefinition]
    ) -> list[SegmentDefinition]:
        """매칭 segment 를 (depth, priority) 로 정렬. 동일 키 다중 → MergeConflictError."""
        keyed: list[tuple[int, int, SegmentDefinition]] = []
        for seg in matched:
            depth = len(ancestor_chain(seg.segment_id, dict(segments)))
            keyed.append((depth, seg.priority, seg))
        # 모호성 검사: 같은 (depth, priority) 가 2개 이상이면 순서 불명 → 명시 해소 요구.
        seen: dict[tuple[int, int], str] = {}
        for depth, prio, seg in keyed:
            k = (depth, prio)
            if k in seen:
                raise MergeConflictError(
                    f"동일 (depth={depth}, priority={prio}) segment 다중 매칭 — "
                    f"순서 모호: {seen[k]!r} vs {seg.segment_id!r}. "
                    "priority 를 달리해 명시적으로 해소할 것 (6-a)."
                )
            seen[k] = seg.segment_id
        keyed.sort(key=lambda t: (t[0], t[1]))
        return [seg for _, _, seg in keyed]

    @staticmethod
    def combine(
        acc: PolicyContribution, contribution: PolicyContribution, spec: MergeSpec
    ) -> PolicyContribution:
        """누적값 ``acc`` 에 ``contribution`` 을 ``spec`` 으로 얹는다."""
        if spec.required_enrichments == "replace":
            re = tuple(contribution.required_enrichments)
        else:  # union
            re = _union_preserve(
                acc.required_enrichments, contribution.required_enrichments
            )
        cutoff = _combine_cutoff(
            acc.cutoff_rules, contribution.cutoff_rules, spec.cutoff_rules
        )
        return PolicyContribution(required_enrichments=re, cutoff_rules=cutoff)

    @classmethod
    def merge(
        cls, steps: list[tuple[PolicyContribution, MergeSpec]]
    ) -> PolicyContribution:
        """(contribution, spec) step 들을 general→specific 순으로 fold."""
        acc = PolicyContribution()
        for contribution, spec in steps:
            acc = cls.combine(acc, contribution, spec)
        return acc
