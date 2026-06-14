"""cutoff_validate 단위 테스트 — manifest 화이트리스트 대조 (ADR-0014, findings 2/3).

manifest 는 fixture dict 로 주입 (파일 의존 없음 — 순수 검증 로직 격리). 실제 코드-동기는
tests/architecture/test_methods_manifest_sync.py 가 별도로 보장.
"""
from __future__ import annotations

import pytest

from domains.policy.domain.cutoff_validate import (
    CutoffContractError,
    make_strict_validator,
    validate_cutoff_rules,
)

pytestmark = pytest.mark.unit

_MANIFEST = {
    "rule_types": ["and", "or", "not", "weighted_sum", "profile_ref", "threshold", "scoring", "signal_presence"],
    "metric_paths": ["annuals_avg.roic", "latest_annual.debt_to_equity", "fcf_positive_years"],
    "enrichment_metric_paths": ["enrichments.nav_discount.discount_pct"],
    "threshold_ops": ["ge", "le", "gt", "lt", "eq"],
}

# quality_floor 와 동형의 합법 트리.
_GOOD = {
    "type": "and",
    "name": "q",
    "children": [
        {"type": "threshold", "name": "roic", "metric_path": "annuals_avg.roic", "op": "ge", "threshold": 0.10},
        {"type": "threshold", "name": "nav", "metric_path": "enrichments.nav_discount.discount_pct", "op": "ge", "threshold": 0.3},
        {"type": "signal_presence", "name": "cap", "required_any_of": ["dividend_payment"]},
    ],
}


def test_accepts_whitelisted_tree() -> None:
    validate_cutoff_rules(_GOOD, _MANIFEST)  # no raise


def test_rejects_unknown_metric_path() -> None:
    bad = {"type": "threshold", "name": "x", "metric_path": "zzz.fabricated", "op": "ge", "threshold": 1}
    with pytest.raises(CutoffContractError, match="metric_path"):
        validate_cutoff_rules(bad, _MANIFEST)


def test_rejects_ne_op_on_threshold() -> None:
    """finding 3 — selector 에선 합법인 'ne' 가 cutoff threshold 에선 reject."""
    bad = {"type": "threshold", "name": "x", "metric_path": "annuals_avg.roic", "op": "ne", "threshold": 1}
    with pytest.raises(CutoffContractError, match="op"):
        validate_cutoff_rules(bad, _MANIFEST)


def test_rejects_unknown_rule_type() -> None:
    bad = {"type": "magic_rule", "name": "x"}
    with pytest.raises(CutoffContractError, match="rule type"):
        validate_cutoff_rules(bad, _MANIFEST)


def test_rejects_non_mapping_or_missing_type() -> None:
    with pytest.raises(CutoffContractError):
        validate_cutoff_rules({"name": "no-type"}, _MANIFEST)
    with pytest.raises(CutoffContractError):
        validate_cutoff_rules("not-a-dict", _MANIFEST)


def test_rejects_nested_bad_metric() -> None:
    bad = {
        "type": "and", "name": "root",
        "children": [{"type": "threshold", "name": "x", "metric_path": "not.allowed", "op": "ge", "threshold": 1}],
    }
    with pytest.raises(CutoffContractError, match=r"children\[0\]"):
        validate_cutoff_rules(bad, _MANIFEST)


def test_weighted_sum_and_scoring_validated() -> None:
    good = {
        "type": "weighted_sum", "name": "ws", "pass_score": 0.5,
        "children": [
            {"rule": {"type": "scoring", "name": "s", "metric_path": "annuals_avg.roic", "method": "linear"}, "weight": 1.0},
        ],
    }
    validate_cutoff_rules(good, _MANIFEST)  # no raise
    bad = {
        "type": "weighted_sum", "name": "ws", "pass_score": 0.5,
        "children": [
            {"rule": {"type": "scoring", "name": "s", "metric_path": "bad.path", "method": "linear"}, "weight": 1.0},
        ],
    }
    with pytest.raises(CutoffContractError):
        validate_cutoff_rules(bad, _MANIFEST)


def test_make_strict_validator_closure() -> None:
    validate = make_strict_validator(_MANIFEST)
    validate(_GOOD)  # no raise
    with pytest.raises(CutoffContractError):
        validate({"type": "threshold", "name": "x", "metric_path": "nope", "op": "ge", "threshold": 1})


def test_empty_manifest_rejects() -> None:
    with pytest.raises(CutoffContractError, match="manifest"):
        validate_cutoff_rules(_GOOD, {})
