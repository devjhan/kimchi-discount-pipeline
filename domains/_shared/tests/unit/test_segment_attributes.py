"""segment_registry.attributes — 선택 속성 namespace + op 검증 단위 테스트 (Task 1)."""
from __future__ import annotations

import pytest

from domains._shared.segment_registry import attributes as attr
from domains._shared.segment_registry.errors import SelectorError


@pytest.mark.unit
def test_known_attribute() -> None:
    assert attr.is_known_attribute("market_cap_krw")
    assert not attr.is_known_attribute("nope_metric")


@pytest.mark.unit
def test_unknown_attribute_kind_raises() -> None:
    with pytest.raises(SelectorError):
        attr.attribute_kind("hallucinated_attr")


@pytest.mark.unit
def test_categorical_rejects_numeric_op() -> None:
    # source_category 는 categorical → ge 금지
    with pytest.raises(SelectorError):
        attr.validate_attribute_op("source_category", "ge")
    # eq 는 허용
    attr.validate_attribute_op("source_category", "eq")


@pytest.mark.unit
def test_numeric_attribute_allows_all_ops() -> None:
    for op in ("ge", "gt", "le", "lt", "eq", "ne"):
        attr.validate_attribute_op("market_cap_krw", op)


@pytest.mark.unit
def test_unknown_op_raises() -> None:
    with pytest.raises(SelectorError):
        attr.validate_attribute_op("market_cap_krw", "approx")


@pytest.mark.unit
def test_compare_numeric() -> None:
    assert attr.compare("ge", 10, 5)
    assert not attr.compare("lt", 10, 5)
    assert attr.compare("eq", 5, 5)


@pytest.mark.unit
def test_compare_categorical_eq_ne() -> None:
    assert attr.compare("eq", "holding_company", "holding_company")
    assert attr.compare("ne", "kospi", "kosdaq")


@pytest.mark.unit
def test_compare_numeric_op_on_string_raises() -> None:
    with pytest.raises(SelectorError):
        attr.compare("ge", "abc", 5)
