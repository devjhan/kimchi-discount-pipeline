"""nav_discount_narrowing detector — 지주사 NAV 할인 좁힘 (a_type primary).

구 ``catalyst_scan.detect_nav_discount_narrowing`` 이전. NAV 시계열 store
(``domains/_shared/nav_history``) 에서 parent 별 premium_pct narrowing 검출.

parent 목록 = config ``holding_companies`` 명시값, 없으면 ``nav_history.list_parents()``
로 store 에 history 가 쌓인 parent 자동 발견 (writer = universe nav_discount enricher,
B-2). 양쪽 모두 비면 skip warning (운용 초반 정상 — 누적 ≥2일 후 발화). 구 helper 의
``CatalystEvent(event_date=...)``
호출은 dataclass 8 필드와 불일치라 실제론 도달 불가능했던 dead path — 본 포트는
well-formed event (``detected_at`` set, ``event_date`` drop; latest_date 는 metadata
에 이미 존재) 로 교정한다 (production parents=[] 이라 golden-diff 무영향).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from domains._shared.nav_history import detect_narrowing, list_parents, load_nav_history
from domains.catalyst.detectors.base import CatalystDetector, DetectContext, DetectResult
from domains.catalyst.domain.event import CatalystEvent
from domains.catalyst.detectors.registry import register_detector


@register_detector("nav_discount_narrowing")
@dataclass(frozen=True)
class NavDiscountNarrowingDetector(CatalystDetector):
    name: str
    enabled: bool
    delta_threshold: float
    lookback_days: int
    holding_companies: tuple[str, ...] = field(default_factory=tuple)

    @classmethod
    def from_spec(cls, spec: dict[str, Any]) -> "NavDiscountNarrowingDetector":
        return cls(
            name=str(spec["name"]),
            enabled=bool(spec.get("enabled", True)),
            delta_threshold=float(spec.get("delta_threshold", -0.05)),
            lookback_days=int(spec.get("lookback_days", 60)),
            holding_companies=tuple(spec.get("holding_companies") or []),
        )

    def detect(self, ctx: DetectContext) -> DetectResult:
        out: list[CatalystEvent] = []
        warnings: list[str] = []
        # config 명시값 우선, 없으면 nav-history store 에 history 보유 parent 자동 발견.
        parents = list(self.holding_companies) or list_parents()
        if not parents:
            warnings.append(
                "nav_discount_narrowing: holding_companies_subsidiaries manual map 비어있음 — skip"
            )
            return DetectResult((), tuple(warnings))

        insufficient = 0
        for parent in parents:
            history = load_nav_history(parent, lookback_days=self.lookback_days)
            if len(history) < 2:
                insufficient += 1
                continue
            narrowed = detect_narrowing(history, self.delta_threshold)
            if not narrowed:
                continue
            name = ctx.universe.get(parent, parent)
            catalyst_id = (
                f"navnarrow_{parent}_{narrowed['earliest_date']}_{narrowed['latest_date']}"
            )
            citations = narrowed.get("citations") or []
            out.append(
                CatalystEvent(
                    catalyst_id=catalyst_id,
                    ticker=parent,
                    name=name,
                    catalyst_type="nav_discount_narrowing",
                    trigger_class="a_type",
                    detected_at=ctx.fetched_at,
                    source_citation=citations[0]
                    if citations
                    else f"NAV_CACHE@{ctx.date}={catalyst_id}",
                    metadata={
                        "earliest_date": narrowed["earliest_date"],
                        "latest_date": narrowed["latest_date"],
                        "earliest_premium_pct": narrowed["earliest_premium_pct"],
                        "latest_premium_pct": narrowed["latest_premium_pct"],
                        "delta": narrowed["delta"],
                        "delta_threshold_abs": narrowed["delta_threshold_abs"],
                        "additional_citations": list(citations[1:]),
                    },
                )
            )
        if insufficient > 0:
            warnings.append(
                f"nav_discount_narrowing: {insufficient}/{len(parents)} parents 시계열 < 2 — "
                "1차 운용 초반 정상 (lookback 충족까지 대기)"
            )
        return DetectResult(tuple(out), tuple(warnings))
