"""두 프로파일 비교 — drift detection (commit gate domain rule).

policy 가 소유한 drift 정책 + screener rule-tree 지식이므로 ``domains/policy/domain``
에 둔다 (유일 소비자 = policy/application/commit). ``_shared`` 공유 커널은 ≥2 도메인이
쓰는 contract+storage(schema/serde/registry)만 — drift 판정은 policy 단독 사용이라
rule-of-three 미충족이었고, screener rule-tree 내부구조 지식을 공유 커널에 두는 것은
no-business-logic 위반이라 이쪽으로 이전. 순수 비교 — I/O 없음.

``_collect_thresholds`` 의 threshold 노드 수집은 screener ``factory._collect_rule_names``
와 의도적 isomorphic 복제 — private import 대신 자체 구현으로 도메인 경계를 보존한다.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from domains._shared.profile_registry.schema import EnrichCutoffProfile


@dataclass(frozen=True)
class Drift:
    """이전 프로파일 대비 변화량."""

    enrichments_added: tuple[str, ...]
    enrichments_removed: tuple[str, ...]
    changed_thresholds: Mapping[str, tuple[float, float]]  # rule_name -> (old, new)
    max_threshold_delta: float  # max |new-old|/|old|


def compute_drift(
    prev: EnrichCutoffProfile | None,
    new_required: tuple[str, ...],
    new_cutoff_rules: Mapping[str, Any],
) -> Drift:
    """prev (없으면 initial commit) 대비 신규 (required + cutoff_rules) 의 drift."""
    if prev is None:
        return Drift((), (), {}, 0.0)  # initial commit
    old_e, new_e = set(prev.required_enrichments), set(new_required)
    old_t = _collect_thresholds(prev.cutoff_rules)
    new_t = _collect_thresholds(new_cutoff_rules)
    changed: dict[str, tuple[float, float]] = {}
    max_delta = 0.0
    for name in old_t.keys() & new_t.keys():
        o, n = old_t[name], new_t[name]
        if o != n:
            changed[name] = (o, n)
            if o != 0:
                max_delta = max(max_delta, abs(n - o) / abs(o))
    return Drift(
        enrichments_added=tuple(sorted(new_e - old_e)),
        enrichments_removed=tuple(sorted(old_e - new_e)),
        changed_thresholds=changed,
        max_threshold_delta=max_delta,
    )


def _collect_thresholds(spec: Mapping[str, Any]) -> dict[str, float]:
    """rule dict-tree 재귀 walk — threshold 노드의 {name: threshold} 수집.

    weighted_sum children 의 ``{"rule": {...}, "weight": ...}`` 래핑도 처리
    (factory._collect_rule_names 동형).
    """
    out: dict[str, float] = {}
    if not isinstance(spec, Mapping):
        return out
    if spec.get("type") == "threshold":
        name = spec.get("name")
        thr = spec.get("threshold")
        if isinstance(name, str) and isinstance(thr, (int, float)) and not isinstance(thr, bool):
            out[name] = float(thr)
    for key in ("children", "inner"):
        v = spec.get(key)
        if isinstance(v, list):
            for c in v:
                if isinstance(c, Mapping):
                    out.update(_collect_thresholds(c.get("rule", c)))
        elif isinstance(v, Mapping):
            out.update(_collect_thresholds(v))
    return out
