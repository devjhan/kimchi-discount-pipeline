"""선택 속성(selection-attribute) namespace 화이트리스트 — selector 의 단일 어휘 권위.

``governance/policy/methods_manifest.yaml`` 의 ``selection_attributes`` 섹션이 본 namespace
의 투영이다 (ADR-0014, 코드 SSoT 생성물): selector 의 rule-based leaf 가 참조할 수
있는 속성 이름을 *여기서만* 정의한다. 화이트리스트 밖 이름 = 환각 → ``SelectorError``.

**5-a 결정**: 본 namespace 는 screener 의 깊은 재무 ``metric_path`` resolver 와 완전히
분리된 *bc-independent 선택 속성* 이다. 여기에 등장하는 값은 segment 멤버십 판정에만
쓰이며, 재무 cutoff 평가(RuleFactory)와 어휘를 공유하지 않는다.

속성 분류:
- numeric — ``ge/gt/le/lt/eq/ne`` 비교 가능 (예: market_cap_krw).
- categorical — ``eq/ne`` 만 의미 있음 (예: source_category).

신규 속성 추가 = 본 화이트리스트에 한 줄 + 빌드 단계(Task 9)가 그 값을 materialize
하도록 보장. 코드 다른 곳에서 raw 문자열로 속성을 만들지 말 것.
"""
from __future__ import annotations

from domains._shared.segment_registry.errors import SelectorError

# ----------------------------------------------------------------------
# 비교 연산자 — numeric / categorical 공통 op 어휘.
# ----------------------------------------------------------------------
NUMERIC_OPS: frozenset[str] = frozenset({"ge", "gt", "le", "lt", "eq", "ne"})
CATEGORICAL_OPS: frozenset[str] = frozenset({"eq", "ne"})
ALL_OPS: frozenset[str] = NUMERIC_OPS | CATEGORICAL_OPS

# ----------------------------------------------------------------------
# 선택 속성 namespace — name → kind ("numeric" | "categorical").
# ----------------------------------------------------------------------
SELECTION_ATTRIBUTES: dict[str, str] = {
    # 규모 / 유동성
    "market_cap_krw": "numeric",
    "avg_daily_value_krw": "numeric",
    # 발견 / 분류 메타
    "source_category": "categorical",
    "listing_market": "categorical",  # KOSPI | KOSDAQ | KONEX
    # enrichment 파생값 (universe Stage 1 산출)
    "nav_discount_pct": "numeric",
    "spread_zscore": "numeric",
}


def is_known_attribute(name: str) -> bool:
    """``name`` 이 선택 속성 화이트리스트에 있나."""
    return name in SELECTION_ATTRIBUTES


def attribute_kind(name: str) -> str:
    """속성의 kind ("numeric" | "categorical"). 미등록 → ``SelectorError``."""
    kind = SELECTION_ATTRIBUTES.get(name)
    if kind is None:
        raise SelectorError(
            f"미등록 선택 속성: {name!r} "
            f"(허용: {sorted(SELECTION_ATTRIBUTES)})"
        )
    return kind


def validate_attribute_op(attribute: str, op: str) -> None:
    """``attribute`` 와 ``op`` 의 정합성 검증. 위반 → ``SelectorError``.

    - 미등록 속성 / 미지원 op → raise.
    - categorical 속성에 numeric-only op (ge/gt/le/lt) → raise.
    """
    kind = attribute_kind(attribute)  # 미등록이면 여기서 raise
    if op not in ALL_OPS:
        raise SelectorError(f"미지원 op: {op!r} (허용: {sorted(ALL_OPS)})")
    if kind == "categorical" and op not in CATEGORICAL_OPS:
        raise SelectorError(
            f"categorical 속성 {attribute!r} 에는 {sorted(CATEGORICAL_OPS)} op 만 허용 "
            f"(got: {op!r})"
        )


def compare(op: str, lhs: object, rhs: object) -> bool:
    """``lhs op rhs`` 평가. numeric op 는 둘 다 수치여야 함.

    수치 변환 불가한 numeric op → ``SelectorError`` (호출부가 UNKNOWN 으로 격하할지
    결정할 수 있도록 raise 가 아니라... 여기서는 raise 하지 않고 호출부가 None 체크 후
    호출하는 계약). lhs/rhs 가 None 인 경우는 호출부에서 미리 걸러야 한다.
    """
    if op == "eq":
        return lhs == rhs
    if op == "ne":
        return lhs != rhs
    # 이하 numeric ops
    try:
        a = float(lhs)  # type: ignore[arg-type]
        b = float(rhs)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise SelectorError(
            f"numeric op {op!r} 에 비수치 피연산자: lhs={lhs!r} rhs={rhs!r}"
        ) from exc
    if op == "ge":
        return a >= b
    if op == "gt":
        return a > b
    if op == "le":
        return a <= b
    if op == "lt":
        return a < b
    raise SelectorError(f"미지원 op: {op!r}")
