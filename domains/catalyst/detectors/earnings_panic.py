"""earnings_panic detector — 실적 발표 후 1일 급락 forced selling (b_type primary).

구 ``catalyst_scan.detect_earnings_panic`` (파일 read) + ``stage3_earnings_panic``
(DART 발표 + KIS/Yahoo 가격) 를 합쳐 in-memory 처리 — 중간 ``03-earnings-panic.json`` 제거.

drop_threshold 는 spec ``one_day_drop_min`` (양수) 의 음수화 (구 thresholds 흡수).
announcement lookback 은 구 helper CLI 기본(30) 보존. G8 fetch-degradation warning
(DART 미가용 / 가격 skip) 은 구 flow 에서 별도 파일에 siloed 됐으나 fold 후 unified
출력 warnings 로 surface — healthy run 에선 0건이라 03-catalyst-events.json byte 호환.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from domains.catalyst import _boundary
from domains.catalyst.detectors.base import CatalystDetector, DetectContext, DetectResult
from domains.catalyst.domain.event import CatalystEvent
from domains.catalyst.detectors.registry import register_detector
from domains.catalyst.io.earnings_panic_fetch import (
    discover_earnings_announcements,
    evaluate_announcement,
)


@register_detector("earnings_panic")
@dataclass(frozen=True)
class EarningsPanicDetector(CatalystDetector):
    name: str
    enabled: bool
    lookback_days: int
    one_day_drop_min: float

    @classmethod
    def from_spec(cls, spec: dict[str, Any]) -> "EarningsPanicDetector":
        return cls(
            name=str(spec["name"]),
            enabled=bool(spec.get("enabled", True)),
            lookback_days=int(spec.get("lookback_days", 30)),
            one_day_drop_min=float(spec.get("one_day_drop_min", 0.10)),
        )

    def detect(self, ctx: DetectContext) -> DetectResult:
        warnings: list[str] = []
        drop_threshold = -abs(self.one_day_drop_min)
        env = dict(ctx.env)
        universe_market = dict(ctx.universe_market)
        if not universe_market:
            return DetectResult((), ())

        anns, ann_warns = discover_earnings_announcements(
            env,
            end_date=ctx.date,
            lookback_days=self.lookback_days,
            universe_codes=set(universe_market.keys()),
        )
        warnings.extend(ann_warns)

        out: list[CatalystEvent] = []
        seen: set[str] = set()
        for ann in anns:
            e = evaluate_announcement(
                ann,
                env=env,
                universe_market=universe_market,
                drop_threshold=drop_threshold,
                allow_yahoo=ctx.allow_yahoo,
                end_date=ctx.date,
                fetched_at=ctx.fetched_at,
            )
            if e.skip_reason:
                warnings.append(f"{e.ticker} skip: {e.skip_reason}")
            if not e.triggered:
                continue
            if e.ticker not in ctx.universe:  # G14
                continue
            cid = f"EARNPANIC-{e.rcept_dt}-{e.rcept_no}"
            if cid in seen:
                continue
            seen.add(cid)
            cites = list(e.citations or [])
            primary_cite = (
                cites[0]
                if cites
                else _boundary.format_citation("DART", e.rcept_dt, {"rcept_no": e.rcept_no})
            )
            out.append(
                CatalystEvent(
                    catalyst_id=cid,
                    ticker=e.ticker,
                    name=ctx.universe[e.ticker],
                    catalyst_type="earnings_panic",
                    trigger_class="b_type",
                    detected_at=ctx.fetched_at,
                    source_citation=primary_cite,
                    metadata={
                        "report_nm": e.report_nm,
                        "rcept_no": e.rcept_no,
                        "rcept_dt": e.rcept_dt,
                        "price_d_minus_1": e.price_d_minus_1,
                        "price_d_plus_1": e.price_d_plus_1,
                        "one_day_drop_pct": e.one_day_drop_pct,
                        "threshold": e.threshold,
                        "price_source": e.price_source,
                        "additional_citations": cites[1:] if len(cites) > 1 else [],
                    },
                )
            )
        return DetectResult(tuple(out), tuple(warnings))
