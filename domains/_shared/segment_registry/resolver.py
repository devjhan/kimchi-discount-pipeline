"""SegmentResolver — ticker → 합성 EnrichCutoffProfile (bc-independent).

per-ticker(profile_registry) 와 whole-universe(default) 사이의 segment 계층을 해소한다:

1. 등록된 segment 전체 로드 + 순환 검출.
2. 주입된 VectorIndexPort 로 ticker 의 scalar 속성 + concept cosine / top-k 멤버를 모아
   ``ResolvedRow`` 구성. 임베딩 미적재 → concept score None → semantic leaf UNKNOWN
   (G8 날조 금지 / G11 default-no-action).
3. SelectorEngine 으로 매칭 segment 판정 → MergeEngine 으로 (depth, priority) 정렬 +
   명시적 per-field 합성. 동일 (depth, priority) 다중 매칭 → MergeConflictError.
4. matched segment 의 profile_ref(named PolicyContribution) + per-ticker
   EnrichCutoffProfile + (선택) whole-universe default 를 fold → 합성 EnrichCutoffProfile.
5. semantic 멤버십은 ``EMBED@<ts>=<concept>:<score>`` (G7 형식) provenance citation 으로 기록.

``screener`` / ``universe`` 를 import 하지 않는다 — 소비처가 본 resolver 를 주입받아
``rule_for`` / ``profile_for`` / ``required_enrichments_for`` closure 로 위임한다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

from domains._shared.profile_registry.schema import (
    SCHEMA_VERSION as PROFILE_SCHEMA_VERSION,
)
from domains._shared.profile_registry.schema import EnrichCutoffProfile, Provenance
from domains._shared.segment_registry.errors import SelectorError
from domains._shared.segment_registry.merge import MergeEngine
from domains._shared.segment_registry.registry import detect_cycle
from domains._shared.segment_registry.schema import (
    MergeSpec,
    PolicyContribution,
    SegmentDefinition,
)
from domains._shared.segment_registry.selector import (
    TRUE,
    ResolvedRow,
    SelectorEngine,
    collect_concepts,
)

try:  # _shared 는 infrastructure._common import 허용 (platform utility)
    from infrastructure._common.utils import now_iso_kst as _default_now_iso
except Exception:  # noqa: BLE001 — 테스트/격리 환경 fallback

    def _default_now_iso() -> str:  # type: ignore[misc]
        return ""


# 주입 의존 타입 alias (구조적).
NamedProfileLookup = Callable[[str], "PolicyContribution | None"]
PerTickerLookup = Callable[[str], "EnrichCutoffProfile | None"]

_PASS_RULE: dict[str, Any] = {"type": "and", "name": "segment_pass", "children": []}


@dataclass(frozen=True)
class Resolution:
    """resolve 결과 — 합성 profile + 진단 (audit / 디버깅)."""

    profile: EnrichCutoffProfile | None
    matched_segment_ids: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    citations: tuple[str, ...] = ()


@dataclass
class SegmentResolver:
    """segment 계층 해소기. 의존은 모두 주입 (bc-independent)."""

    segments: Mapping[str, SegmentDefinition]
    known_concepts: frozenset[str]
    vector_index: Any  # VectorIndexPort (구조적)
    named_profile_for: NamedProfileLookup
    per_ticker_for: PerTickerLookup
    default_contribution: PolicyContribution | None = None
    per_ticker_merge: MergeSpec = field(default_factory=MergeSpec)
    embedding_model_id: str = ""
    now_iso: Callable[[], str] = _default_now_iso

    def __post_init__(self) -> None:
        detect_cycle(dict(self.segments))  # 순환 → SegmentCycleError (구성 시점 fail-fast)
        self._engine = SelectorEngine(self.known_concepts)

    # ------------------------------------------------------------------
    def resolve(self, ticker: str) -> Resolution:
        """``ticker`` 에 대한 합성 EnrichCutoffProfile. 미해당 + per-ticker 부재 → profile=None."""
        row = self._build_row(ticker)
        warnings: list[str] = []
        citations: list[str] = []
        matched: list[SegmentDefinition] = []

        for seg in self.segments.values():
            try:
                self._engine.validate(seg.selector)
            except SelectorError as exc:
                warnings.append(f"segment {seg.segment_id}: 잘못된 selector — {exc}")
                continue
            res = self._engine.evaluate(seg.selector, row)
            warnings.extend(res.warnings)
            if res.value == TRUE:
                matched.append(seg)
                ts = self.now_iso()
                for concept, score in res.semantic_scores.items():
                    citations.append(f"EMBED@{ts}={concept}:{score:.4f}")

        ordered = MergeEngine.order_matched(matched, self.segments)  # may raise MergeConflictError

        steps: list[tuple[PolicyContribution, MergeSpec]] = []
        if self.default_contribution is not None:
            steps.append((self.default_contribution, MergeSpec()))
        for seg in ordered:
            contribution = self.named_profile_for(seg.profile_ref)
            if contribution is None:
                warnings.append(
                    f"segment {seg.segment_id}: profile_ref {seg.profile_ref!r} 미등록 — skip"
                )
                continue
            steps.append((contribution, seg.merge_spec))

        per_ticker = self.per_ticker_for(ticker)
        if per_ticker is not None:
            steps.append(
                (
                    PolicyContribution(
                        required_enrichments=tuple(per_ticker.required_enrichments),
                        cutoff_rules=dict(per_ticker.cutoff_rules),
                    ),
                    self.per_ticker_merge,
                )
            )

        if not steps:
            return Resolution(
                profile=None,
                matched_segment_ids=tuple(s.segment_id for s in ordered),
                warnings=tuple(warnings),
                citations=tuple(citations),
            )

        merged = MergeEngine.merge(steps)
        cutoff = dict(merged.cutoff_rules) if merged.cutoff_rules else dict(_PASS_RULE)
        profile = EnrichCutoffProfile(
            ticker=ticker,
            schema_version=PROFILE_SCHEMA_VERSION,
            profile_version=1,
            required_enrichments=tuple(merged.required_enrichments),
            cutoff_rules=cutoff,
            provenance=Provenance(
                committed_at=self.now_iso(),
                committed_by="segment-resolver",
                trigger=f"segment-resolve:{ticker}",
                citations=tuple(citations),
                rationale_ko=(
                    "segment 계층 합성: "
                    + (", ".join(s.segment_id for s in ordered) or "default/per-ticker only")
                ),
            ),
            description="resolved by segment_registry",
        )
        return Resolution(
            profile=profile,
            matched_segment_ids=tuple(s.segment_id for s in ordered),
            warnings=tuple(warnings),
            citations=tuple(citations),
        )

    # ------------------------------------------------------------------
    def _build_row(self, ticker: str) -> ResolvedRow:
        """모든 segment selector 가 참조하는 concept 의 cosine/top-k + scalar 속성 수집."""
        concepts: set[str] = set()
        topk: dict[str, int] = {}
        for seg in self.segments.values():
            concepts |= collect_concepts(seg.selector)
            for concept, k in _topk_usages(seg.selector).items():
                topk[concept] = max(topk.get(concept, 0), k)

        scalars = dict(self.vector_index.attributes_for(ticker))
        concept_scores: dict[str, float | None] = {}
        for concept in concepts:
            concept_scores[concept] = self.vector_index.cosine(ticker, concept)

        topk_members: dict[str, frozenset[str]] = {}
        for concept, k in topk.items():
            members = self.vector_index.top_k(concept, k)
            topk_members[concept] = frozenset(t for t, _ in members)

        return ResolvedRow(
            ticker=ticker,
            scalars=scalars,
            concept_scores=concept_scores,
            concept_topk_members=topk_members,
        )


def _topk_usages(spec: Mapping[str, Any]) -> dict[str, int]:
    """selector tree 의 semantic_similarity(top_k) leaf 에서 concept→k 수집."""
    out: dict[str, int] = {}
    if not isinstance(spec, Mapping):
        return out
    if spec.get("type") == "semantic_similarity" and "top_k" in spec:
        c = spec.get("concept")
        if isinstance(c, str):
            try:
                out[c] = max(out.get(c, 0), int(spec["top_k"]))
            except (TypeError, ValueError):
                pass
    children = spec.get("children")
    if isinstance(children, (list, tuple)):
        for c in children:
            for k, v in _topk_usages(c).items():
                out[k] = max(out.get(k, 0), v)
    inner = spec.get("inner")
    if isinstance(inner, Mapping):
        for k, v in _topk_usages(inner).items():
            out[k] = max(out.get(k, 0), v)
    return out
