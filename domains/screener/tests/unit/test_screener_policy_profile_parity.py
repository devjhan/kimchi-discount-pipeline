"""ADR-0013 Q2 golden parity — global profile 마이그레이션이 RuleFactory 산출을 불변으로 둠.

quality_floor 가 구 ``screener-profile-v1``(``rule:`` 키) 에서 통합 ``policy-profile-v1``
(``cutoff_rules:`` 키, scope=global) 로 이전됐다. ``_boundary.load_profile`` 어댑터가
통합 스키마를 RuleFactory 가 기대하는 rule-dict 로 투영하므로, RuleFactory 가 빌드한
Rule 트리는 마이그레이션 전(legacy 형태)과 **byte-identical** 이어야 한다 (flag OFF parity).
"""
from __future__ import annotations

import pytest

from domains.screener import _boundary
from domains.screener.rules.factory import RuleFactory

pytestmark = pytest.mark.unit

# 마이그레이션 전 quality_floor 의 rule 트리 (golden 참조 — on-disk 와 독립한 리터럴).
_GOLDEN_RULE_TREE = {
    "type": "and",
    "name": "quality_floor",
    "children": [
        {"type": "threshold", "name": "roic_3y_avg", "metric_path": "annuals_avg.roic",
         "period_years": 3, "op": "ge", "threshold": 0.10},
        {"type": "threshold", "name": "debt_to_equity",
         "metric_path": "latest_annual.debt_to_equity", "op": "le", "threshold": 1.0},
        {"type": "threshold", "name": "interest_coverage",
         "metric_path": "latest_annual.interest_coverage", "op": "ge", "threshold": 4.0},
        {"type": "threshold", "name": "fcf_positive_years",
         "metric_path": "fcf_positive_years", "period_years": 3, "op": "ge", "threshold": 3},
        {"type": "threshold", "name": "fcf_to_revenue_ttm",
         "metric_path": "ttm.fcf_to_revenue", "op": "ge", "threshold": 0.05},
        {"type": "signal_presence", "name": "capital_allocation",
         "required_any_of": ["dividend_payment", "treasury_share_purchase",
                             "treasury_share_cancellation"]},
    ],
}

# 마이그레이션 전 on-disk 형태 (screener-profile-v1, rule: 키).
_LEGACY_PROFILE_DICT = {
    "schema": "screener-profile-v1",
    "name": "quality_floor",
    "version": 1,
    "description": "ROIC + 부채 + 현금흐름 + 자본배분 기본 퀄리티 통과 게이트",
    "qualitative_lenses": ["moat", "자본배분", "회계 적신호", "지주사"],
    "rule": _GOLDEN_RULE_TREE,
}


def _tax_rate(strategy: dict) -> float:
    return float((strategy.get("constants") or {}).get("tax_rate", 0.22))


def test_on_disk_migrated_profile_rule_matches_golden() -> None:
    """on-disk policy-profile-v1 → load_profile 어댑터가 golden rule 트리를 그대로 복원."""
    adapted = _boundary.load_profile("quality_floor")
    assert adapted["rule"] == _GOLDEN_RULE_TREE
    assert adapted["name"] == "quality_floor"
    # qualitative_lenses 보존 (stage2-quality-lens skill 소비).
    assert len(adapted["qualitative_lenses"]) == 4


def test_rulefactory_tree_byte_identical_legacy_vs_migrated() -> None:
    """RuleFactory 가 빌드한 Rule 트리: 마이그레이션(on-disk) == legacy(rule: 키) 형태."""
    strategy = _boundary.load_strategy("default")
    hard_guards = _boundary.load_hard_guards()
    tax = _tax_rate(strategy)

    migrated = _boundary.load_profile("quality_floor")
    tree_migrated = RuleFactory.build_strategy(
        strategy, {"quality_floor": migrated}, hard_guards, tax_rate=tax
    )
    tree_legacy = RuleFactory.build_strategy(
        strategy, {"quality_floor": _LEGACY_PROFILE_DICT}, hard_guards, tax_rate=tax
    )
    assert tree_migrated == tree_legacy
