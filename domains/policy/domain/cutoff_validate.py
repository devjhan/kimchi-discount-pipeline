"""strict cutoff_rules 검증 — manifest 화이트리스트 대조 (ADR-0014, findings 2/3).

기존 ``shape_validate_cutoff_rules`` 는 ``type`` 키 존재만 봤다(shape-only) — 잘못된
``metric_path`` / ``op`` / ``type`` 은 screener 로드 시점에 caution 으로 *조용히* degrade
됐다(finding 3). 본 모듈은 그 검증을 **commit 시점** 으로 끌어와 결정론적으로 reject 한다.

bc-independence (불변식 A): 화이트리스트 어휘는 screener 코드가 소유하지만, 본 검증은
screener 를 import 하지 않고 ``methods_manifest.yaml`` 을 **DATA** 로 받아 대조한다. manifest
자체의 코드-동기는 ``test_methods_manifest_sync`` arch test 가 보장한다.

순수 — I/O 없음. manifest dict 는 caller(composition root / 테스트)가 주입.
"""
from __future__ import annotations

from typing import Any, Callable, Mapping

# 화이트리스트가 필요 없는(자식만 재귀) 합성/특수 노드.
_COMPOSITE = frozenset({"and", "or"})


class CutoffContractError(ValueError):
    """cutoff_rules 가 manifest 화이트리스트(type/metric_path/op)를 위반."""


def validate_cutoff_rules(cutoff_rules: Any, manifest: Mapping[str, Any]) -> None:
    """cutoff_rules dict-tree 를 manifest 화이트리스트로 검증. 위반 → CutoffContractError.

    검사:
    - 모든 노드 ``type`` ∈ manifest['rule_types'].
    - ``threshold`` / ``scoring`` 노드 ``metric_path`` ∈ metric_paths ∪ enrichment_metric_paths.
    - ``threshold`` 노드 ``op`` ∈ manifest['threshold_ops'] (``ne`` 등 미지원 op reject).
    룰 *값* 의 의미(임계 타당성 등)는 검증하지 않음 — 화이트리스트 대조만.
    """
    if not isinstance(cutoff_rules, Mapping) or "type" not in cutoff_rules:
        raise CutoffContractError("cutoff_rules는 'type' 키를 가진 Rule dict-tree여야 함")

    rule_types = frozenset(manifest.get("rule_types") or ())
    metric_paths = frozenset(manifest.get("metric_paths") or ()) | frozenset(
        manifest.get("enrichment_metric_paths") or ()
    )
    threshold_ops = frozenset(manifest.get("threshold_ops") or ())
    if not rule_types or not metric_paths or not threshold_ops:
        raise CutoffContractError(
            "manifest 화이트리스트 비어 있음 — methods_manifest.yaml 손상/미생성"
        )

    _walk(cutoff_rules, rule_types, metric_paths, threshold_ops, path="cutoff_rules")


def make_strict_validator(
    manifest: Mapping[str, Any],
) -> Callable[[Any], None]:
    """commit_profile(validate_rules=...) 주입용 클로저 — manifest 를 바인딩."""

    def _validate(cutoff_rules: Any) -> None:
        validate_cutoff_rules(cutoff_rules, manifest)

    return _validate


def _walk(
    node: Any,
    rule_types: frozenset[str],
    metric_paths: frozenset[str],
    threshold_ops: frozenset[str],
    *,
    path: str,
) -> None:
    if not isinstance(node, Mapping):
        raise CutoffContractError(f"{path}: Rule 노드는 Mapping 이어야 함 (got {type(node).__name__})")
    rtype = node.get("type")
    if rtype not in rule_types:
        raise CutoffContractError(
            f"{path}: 미지원 rule type {rtype!r} (허용: {sorted(rule_types)})"
        )

    if rtype == "threshold":
        _check_metric(node, metric_paths, path)
        op = node.get("op")
        if op not in threshold_ops:
            raise CutoffContractError(
                f"{path}: threshold op {op!r} 미지원 (허용: {sorted(threshold_ops)}; "
                "selector 의 'ne' 는 cutoff 에서 불가)"
            )
        return
    if rtype == "scoring":
        _check_metric(node, metric_paths, path)
        return
    if rtype == "signal_presence":
        if not node.get("required_any_of"):
            raise CutoffContractError(f"{path}: signal_presence 는 'required_any_of' 필요")
        return
    if rtype == "profile_ref":
        # 참조 대상 해소/검증은 screener 로드 시점 (여기서는 type 합법성만).
        if not node.get("profile"):
            raise CutoffContractError(f"{path}: profile_ref 는 'profile' 이름 필요")
        return
    if rtype in _COMPOSITE:
        children = node.get("children")
        if not isinstance(children, (list, tuple)) or not children:
            raise CutoffContractError(f"{path}: {rtype} 노드는 비어 있지 않은 'children' 필요")
        for i, child in enumerate(children):
            _walk(child, rule_types, metric_paths, threshold_ops, path=f"{path}.children[{i}]")
        return
    if rtype == "not":
        inner = node.get("inner")
        if inner is None:
            raise CutoffContractError(f"{path}: not 노드는 'inner' 필요")
        _walk(inner, rule_types, metric_paths, threshold_ops, path=f"{path}.inner")
        return
    if rtype == "weighted_sum":
        children = node.get("children")
        if not isinstance(children, (list, tuple)) or not children:
            raise CutoffContractError(f"{path}: weighted_sum 노드는 비어 있지 않은 'children' 필요")
        for i, child in enumerate(children):
            if not isinstance(child, Mapping) or "rule" not in child:
                raise CutoffContractError(
                    f"{path}.children[{i}]: weighted_sum child 는 'rule' 키 필요"
                )
            _walk(
                child["rule"], rule_types, metric_paths, threshold_ops,
                path=f"{path}.children[{i}].rule",
            )
        return
    # rule_types 에 있으나 위 분기에 없는 type — 방어적 reject (silent pass 금지).
    raise CutoffContractError(f"{path}: rule type {rtype!r} 검증 분기 미정의")


def _check_metric(node: Mapping[str, Any], metric_paths: frozenset[str], path: str) -> None:
    mp = node.get("metric_path")
    if mp not in metric_paths:
        raise CutoffContractError(
            f"{path}: metric_path {mp!r} 가 화이트리스트 밖 "
            "(methods_manifest.yaml; resolver 소비 불가 = 환각 차단)"
        )
