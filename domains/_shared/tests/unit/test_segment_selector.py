"""segment_registry.selector — SelectorEngine 검증 + 3-값 평가 단위 테스트 (Task 2)."""
from __future__ import annotations

import pytest

from domains._shared.segment_registry.errors import SelectorError
from domains._shared.segment_registry.selector import (
    FALSE,
    TRUE,
    UNKNOWN,
    ResolvedRow,
    SelectorEngine,
    collect_concepts,
)

_MIXED = {
    "type": "and",
    "children": [
        {"type": "semantic_similarity", "concept": "holdco_value_trap", "op": "ge", "threshold": 0.78},
        {"type": "threshold", "attribute": "market_cap_krw", "op": "ge", "threshold": 3e11},
    ],
}


def _engine() -> SelectorEngine:
    return SelectorEngine(known_concepts={"holdco_value_trap"})


@pytest.mark.unit
def test_validate_mixed_ok() -> None:
    _engine().validate(_MIXED)  # no raise


@pytest.mark.unit
def test_validate_unknown_type_raises() -> None:
    with pytest.raises(SelectorError):
        _engine().validate({"type": "xor", "children": []})


@pytest.mark.unit
def test_validate_unknown_attribute_raises() -> None:
    with pytest.raises(SelectorError):
        _engine().validate({"type": "threshold", "attribute": "ghost", "op": "ge", "threshold": 1})


@pytest.mark.unit
def test_validate_unknown_concept_raises() -> None:
    with pytest.raises(SelectorError):
        _engine().validate(
            {"type": "semantic_similarity", "concept": "ghost", "threshold": 0.5}
        )


@pytest.mark.unit
def test_validate_semantic_requires_threshold_or_topk() -> None:
    with pytest.raises(SelectorError):
        _engine().validate({"type": "semantic_similarity", "concept": "holdco_value_trap"})


@pytest.mark.unit
def test_eval_mixed_member() -> None:
    row = ResolvedRow(
        ticker="KR:003550",
        scalars={"market_cap_krw": 5e11},
        concept_scores={"holdco_value_trap": 0.81},
    )
    res = _engine().evaluate(_MIXED, row)
    assert res.value == TRUE and res.is_member
    assert res.semantic_scores == {"holdco_value_trap": 0.81}


@pytest.mark.unit
def test_eval_rule_fails_short_circuits_false() -> None:
    row = ResolvedRow(
        ticker="KR:003550",
        scalars={"market_cap_krw": 1e11},  # < 3e11 → FALSE
        concept_scores={"holdco_value_trap": 0.81},
    )
    assert _engine().evaluate(_MIXED, row).value == FALSE


@pytest.mark.unit
def test_eval_semantic_unavailable_and_unknown() -> None:
    # and: rule TRUE, semantic UNKNOWN → UNKNOWN (멤버로 강제 안 함, G8/G11)
    row = ResolvedRow(
        ticker="KR:003550",
        scalars={"market_cap_krw": 5e11},
        concept_scores={},  # 점수 미가용
    )
    res = _engine().evaluate(_MIXED, row)
    assert res.value == UNKNOWN
    assert not res.is_member
    assert any("semantic score 미가용" in w for w in res.warnings)


@pytest.mark.unit
def test_eval_semantic_unavailable_but_rule_false_is_false() -> None:
    # and: rule FALSE 가 UNKNOWN 을 압도 → FALSE
    row = ResolvedRow(ticker="KR:x", scalars={"market_cap_krw": 1e11}, concept_scores={})
    assert _engine().evaluate(_MIXED, row).value == FALSE


@pytest.mark.unit
def test_or_unknown_semantics() -> None:
    spec = {
        "type": "or",
        "children": [
            {"type": "threshold", "attribute": "market_cap_krw", "op": "ge", "threshold": 3e11},
            {"type": "semantic_similarity", "concept": "holdco_value_trap", "threshold": 0.9},
        ],
    }
    # rule FALSE + semantic UNKNOWN → UNKNOWN
    row = ResolvedRow(ticker="KR:x", scalars={"market_cap_krw": 1e11}, concept_scores={})
    assert _engine().evaluate(spec, row).value == UNKNOWN
    # rule TRUE → TRUE (semantic 무관)
    row2 = ResolvedRow(ticker="KR:y", scalars={"market_cap_krw": 9e11}, concept_scores={})
    assert _engine().evaluate(spec, row2).value == TRUE


@pytest.mark.unit
def test_not_negation_and_unknown() -> None:
    eng = _engine()
    base = {"type": "threshold", "attribute": "market_cap_krw", "op": "ge", "threshold": 3e11}
    spec = {"type": "not", "inner": base}
    assert eng.evaluate(spec, ResolvedRow("KR:x", {"market_cap_krw": 1e11})).value == TRUE
    assert eng.evaluate(spec, ResolvedRow("KR:y", {"market_cap_krw": 9e11})).value == FALSE
    # UNKNOWN → UNKNOWN
    assert eng.evaluate(spec, ResolvedRow("KR:z", {})).value == UNKNOWN


@pytest.mark.unit
def test_categorical_threshold_eq() -> None:
    spec = {"type": "threshold", "attribute": "source_category", "op": "eq", "threshold": "holding_company"}
    eng = SelectorEngine()
    eng.validate(spec)
    assert eng.evaluate(spec, ResolvedRow("KR:x", {"source_category": "holding_company"})).value == TRUE
    assert eng.evaluate(spec, ResolvedRow("KR:y", {"source_category": "manual_addition"})).value == FALSE


@pytest.mark.unit
def test_topk_membership() -> None:
    spec = {"type": "semantic_similarity", "concept": "holdco_value_trap", "top_k": 2}
    eng = _engine()
    eng.validate(spec)
    row = ResolvedRow(
        ticker="KR:003550",
        concept_scores={"holdco_value_trap": 0.7},
        concept_topk_members={"holdco_value_trap": frozenset({"KR:003550", "KR:000880"})},
    )
    assert eng.evaluate(spec, row).value == TRUE
    row_out = ResolvedRow(
        ticker="KR:999999",
        concept_topk_members={"holdco_value_trap": frozenset({"KR:003550"})},
    )
    assert eng.evaluate(spec, row_out).value == FALSE
    # 멤버 집합 미산출 → UNKNOWN
    assert eng.evaluate(spec, ResolvedRow("KR:003550")).value == UNKNOWN


@pytest.mark.unit
def test_collect_concepts() -> None:
    assert collect_concepts(_MIXED) == {"holdco_value_trap"}
