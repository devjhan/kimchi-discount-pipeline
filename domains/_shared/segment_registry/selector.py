"""Selector predicate tree + SelectorEngine — 부분집합 멤버십 판정 (bc-independent).

selector 는 ``and | or | not`` 합성 노드 + **동급(co-equal) leaf** 두 종류로 구성된다
(5-a / 12-a):

- ``threshold`` — rule-based. 선택 속성(attributes.SELECTION_ATTRIBUTES) 1개를
  ``op`` 로 비교. 예: ``{type: threshold, attribute: market_cap_krw, op: ge, threshold: 3e11}``.
- ``semantic_similarity`` — semantic. concept anchor 와의 cosine 으로 판정.
  예: ``{type: semantic_similarity, concept: holdco_value_trap, op: ge, threshold: 0.78}``
  또는 ``{..., top_k: 30}``.

두 leaf 는 같은 합성 노드 아래에서 자유롭게 섞인다 — 위계가 동등하다.

### 3-값 논리 (G8 no-hallucination / G11 default-no-action)

임베딩 키 부재 / 오프라인 / 미적재 → semantic score 부재 → 해당 leaf 는 **UNKNOWN**.
scalar 속성 값 부재도 UNKNOWN. UNKNOWN 은 *날조 금지* 의 표현이다:

- ``and``: 하나라도 FALSE → FALSE; 아니고 UNKNOWN 있으면 → UNKNOWN; else TRUE
- ``or`` : 하나라도 TRUE → TRUE; 아니고 UNKNOWN 있으면 → UNKNOWN; else FALSE
- ``not``: TRUE↔FALSE, UNKNOWN→UNKNOWN

최종 멤버십은 ``result is TRUE`` 일 때만 member. UNKNOWN → 비멤버 + warning (호출부가
수집). 즉 의미 불명을 *멤버로 강제 생성하지 않는다*.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from domains._shared.segment_registry.attributes import (
    compare,
    validate_attribute_op,
)
from domains._shared.segment_registry.errors import SelectorError

# 3-값 논리 상수.
TRUE = "true"
FALSE = "false"
UNKNOWN = "unknown"

_COMPOSITE_TYPES = frozenset({"and", "or", "not"})
_LEAF_TYPES = frozenset({"threshold", "semantic_similarity"})


@dataclass(frozen=True)
class ResolvedRow:
    """단일 ticker 의 selector 평가 입력 — scalar 속성 + concept 점수/멤버십."""

    ticker: str
    scalars: Mapping[str, Any] = field(default_factory=dict)
    """선택 속성 name → 값. 부재 키는 UNKNOWN 으로 격하."""

    concept_scores: Mapping[str, float | None] = field(default_factory=dict)
    """concept_id → cosine score. None / 부재 → UNKNOWN (임베딩 미가용)."""

    concept_topk_members: Mapping[str, frozenset[str]] = field(default_factory=dict)
    """concept_id → top-k 멤버 ticker 집합 (resolver 가 precompute). 부재 → top_k leaf UNKNOWN."""


@dataclass
class EvalResult:
    """selector 평가 결과 — 멤버십 + 진단."""

    value: str  # TRUE | FALSE | UNKNOWN
    warnings: tuple[str, ...] = ()
    semantic_scores: Mapping[str, float] = field(default_factory=dict)
    """평가에 사용된 concept_id → score (provenance / G7 citation 용)."""

    @property
    def is_member(self) -> bool:
        return self.value == TRUE


class SelectorEngine:
    """selector dict-tree 를 검증 + 평가. ``known_concepts`` 주입 (환각 차단)."""

    def __init__(self, known_concepts: frozenset[str] | set[str] | None = None) -> None:
        self._known_concepts = frozenset(known_concepts or ())

    # ------------------------------------------------------------------
    # 검증 — shape / 어휘. 평가 전 1차 방어 (resolver / build 가 호출).
    # ------------------------------------------------------------------
    def validate(self, spec: Mapping[str, Any]) -> None:
        """selector tree 의 문법 + 어휘 검증. 위반 → SelectorError."""
        if not isinstance(spec, Mapping) or "type" not in spec:
            raise SelectorError("selector 노드는 'type' 키를 가진 Mapping 이어야 함")
        rtype = spec["type"]

        if rtype in ("and", "or"):
            children = spec.get("children")
            if not isinstance(children, (list, tuple)) or not children:
                raise SelectorError(f"{rtype} 노드는 비어 있지 않은 'children' 필요")
            for c in children:
                self.validate(c)
            return
        if rtype == "not":
            inner = spec.get("inner")
            if inner is None:
                raise SelectorError("not 노드는 'inner' 필요")
            self.validate(inner)
            return
        if rtype == "threshold":
            attribute = spec.get("attribute")
            op = spec.get("op")
            if not isinstance(attribute, str) or not isinstance(op, str):
                raise SelectorError("threshold leaf 는 'attribute'(str)+'op'(str) 필요")
            if "threshold" not in spec:
                raise SelectorError("threshold leaf 는 'threshold' 값 필요")
            validate_attribute_op(attribute, op)  # 미등록 속성 / 잘못된 op → raise
            return
        if rtype == "semantic_similarity":
            concept = spec.get("concept")
            if not isinstance(concept, str):
                raise SelectorError("semantic_similarity leaf 는 'concept'(str) 필요")
            if self._known_concepts and concept not in self._known_concepts:
                raise SelectorError(
                    f"미등록 concept: {concept!r} "
                    f"(알려진: {sorted(self._known_concepts)})"
                )
            has_threshold = "threshold" in spec
            has_topk = "top_k" in spec
            if not has_threshold and not has_topk:
                raise SelectorError(
                    "semantic_similarity leaf 는 'threshold' 또는 'top_k' 중 하나 필요"
                )
            return
        raise SelectorError(
            f"미지원 selector type: {rtype!r} "
            f"(허용: {sorted(_COMPOSITE_TYPES | _LEAF_TYPES)})"
        )

    # ------------------------------------------------------------------
    # 평가 — 3-값 논리.
    # ------------------------------------------------------------------
    def evaluate(self, spec: Mapping[str, Any], row: ResolvedRow) -> EvalResult:
        """selector tree 를 ``row`` 에 대해 평가. 검증은 호출부가 미리 수행 가정.

        방어적으로 미지원 type 은 SelectorError 를 raise 한다 (silent FALSE 금지).
        """
        rtype = spec["type"]

        if rtype == "and":
            return self._combine_and(
                [self.evaluate(c, row) for c in spec["children"]]
            )
        if rtype == "or":
            return self._combine_or(
                [self.evaluate(c, row) for c in spec["children"]]
            )
        if rtype == "not":
            return self._negate(self.evaluate(spec["inner"], row))
        if rtype == "threshold":
            return self._eval_threshold(spec, row)
        if rtype == "semantic_similarity":
            return self._eval_semantic(spec, row)
        raise SelectorError(f"미지원 selector type: {rtype!r}")

    # ----- leaf 평가 -----
    @staticmethod
    def _eval_threshold(spec: Mapping[str, Any], row: ResolvedRow) -> EvalResult:
        attribute = spec["attribute"]
        op = spec["op"]
        rhs = spec["threshold"]
        lhs = row.scalars.get(attribute)
        if lhs is None:
            return EvalResult(
                UNKNOWN,
                warnings=(f"{row.ticker}: 선택 속성 부재 — {attribute}",),
            )
        try:
            ok = compare(op, lhs, rhs)
        except SelectorError as exc:
            return EvalResult(UNKNOWN, warnings=(f"{row.ticker}: {exc}",))
        return EvalResult(TRUE if ok else FALSE)

    @staticmethod
    def _eval_semantic(spec: Mapping[str, Any], row: ResolvedRow) -> EvalResult:
        concept = spec["concept"]
        # top_k 우선 (leaf 가 명시했으면). top-k 멤버 집합은 resolver precompute.
        if "top_k" in spec:
            members = row.concept_topk_members.get(concept)
            if members is None:
                return EvalResult(
                    UNKNOWN,
                    warnings=(f"{row.ticker}: top_k 멤버 미산출 — concept {concept}",),
                )
            score = row.concept_scores.get(concept)
            used = {concept: float(score)} if score is not None else {}
            return EvalResult(
                TRUE if row.ticker in members else FALSE, semantic_scores=used
            )
        # threshold 경로
        op = spec.get("op", "ge")
        rhs = spec["threshold"]
        score = row.concept_scores.get(concept)
        if score is None:
            return EvalResult(
                UNKNOWN,
                warnings=(
                    f"{row.ticker}: semantic score 미가용 — concept {concept} "
                    "(임베딩 미적재/키부재)",
                ),
            )
        try:
            ok = compare(op, score, rhs)
        except SelectorError as exc:
            return EvalResult(UNKNOWN, warnings=(f"{row.ticker}: {exc}",))
        return EvalResult(
            TRUE if ok else FALSE, semantic_scores={concept: float(score)}
        )

    # ----- 3-값 합성 -----
    @staticmethod
    def _merge_diag(results: list[EvalResult]) -> tuple[tuple[str, ...], dict[str, float]]:
        warns: list[str] = []
        scores: dict[str, float] = {}
        for r in results:
            warns.extend(r.warnings)
            scores.update(r.semantic_scores)
        return tuple(warns), scores

    @classmethod
    def _combine_and(cls, results: list[EvalResult]) -> EvalResult:
        warns, scores = cls._merge_diag(results)
        if any(r.value == FALSE for r in results):
            return EvalResult(FALSE, warnings=warns, semantic_scores=scores)
        if any(r.value == UNKNOWN for r in results):
            return EvalResult(UNKNOWN, warnings=warns, semantic_scores=scores)
        return EvalResult(TRUE, warnings=warns, semantic_scores=scores)

    @classmethod
    def _combine_or(cls, results: list[EvalResult]) -> EvalResult:
        warns, scores = cls._merge_diag(results)
        if any(r.value == TRUE for r in results):
            return EvalResult(TRUE, warnings=warns, semantic_scores=scores)
        if any(r.value == UNKNOWN for r in results):
            return EvalResult(UNKNOWN, warnings=warns, semantic_scores=scores)
        return EvalResult(FALSE, warnings=warns, semantic_scores=scores)

    @staticmethod
    def _negate(r: EvalResult) -> EvalResult:
        flip = {TRUE: FALSE, FALSE: TRUE, UNKNOWN: UNKNOWN}[r.value]
        return EvalResult(flip, warnings=r.warnings, semantic_scores=r.semantic_scores)


def collect_concepts(spec: Mapping[str, Any]) -> set[str]:
    """selector tree 에서 참조된 모든 concept_id 수집 (resolver 의 precompute 용)."""
    out: set[str] = set()
    if not isinstance(spec, Mapping):
        return out
    if spec.get("type") == "semantic_similarity":
        c = spec.get("concept")
        if isinstance(c, str):
            out.add(c)
    children = spec.get("children")
    if isinstance(children, (list, tuple)):
        for c in children:
            out |= collect_concepts(c)
    inner = spec.get("inner")
    if isinstance(inner, Mapping):
        out |= collect_concepts(inner)
    return out
