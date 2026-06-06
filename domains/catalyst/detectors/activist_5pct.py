"""activist_5pct detector — 5% 대량보유 신고 (d_type, augment-only / G15).

구 ``catalyst_scan.detect_activist_5pct`` 이전. 단독 trigger 금지 (orchestrator 가
a/b primary 와 결합 시에만 후보화). ``known_activist_funds`` / ``include_known_funds_only``
는 detector spec 에서 주입 (구 thresholds + universe config 흡수; 기본 필터 OFF).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from functools import partial
from typing import Any

from domains.catalyst import _boundary
from domains.catalyst.detectors.base import CatalystDetector, DetectContext, DetectResult
from domains.catalyst.detectors.registry import register_detector
from domains.catalyst.domain.event import CatalystEvent
from domains._shared.adapters.disclosure_scan import MatchedDisclosure, scan_disclosures

_AUGMENT_NOTE = "G15 — d_type 단독 trigger 금지. a_type 또는 b_type과 결합 시에만 valid."


@register_detector("activist_5pct")
@dataclass(frozen=True)
class Activist5pctDetector(CatalystDetector):
    name: str
    enabled: bool
    lookback_days: int
    include_known_funds_only: bool
    known_activist_funds: tuple[str, ...] = field(default_factory=tuple)

    @classmethod
    def from_spec(cls, spec: dict[str, Any]) -> "Activist5pctDetector":
        return cls(
            name=str(spec["name"]),
            enabled=bool(spec.get("enabled", True)),
            lookback_days=int(spec.get("lookback_days", 30)),
            include_known_funds_only=bool(spec.get("include_known_funds_only", False)),
            known_activist_funds=tuple(spec.get("known_activist_funds") or []),
        )

    def detect(self, ctx: DetectContext) -> DetectResult:
        warnings: list[str] = []
        api_key = ctx.env.get("DART_API_KEY", "")
        if not api_key:
            warnings.append("DART_API_KEY missing → activist_5pct_filing skipped")
            return DetectResult((), tuple(warnings))
        end_dt = datetime.strptime(ctx.date, "%Y-%m-%d")
        bgn_dt = end_dt - timedelta(days=self.lookback_days)
        out: list[CatalystEvent] = []

        def _keep(md: MatchedDisclosure) -> bool:
            """G14 universe 게이트 + (옵션) known-funds 필터 — dedup 전 적용."""
            if md.ticker not in ctx.universe:
                return False
            if self.include_known_funds_only:
                flr_nm = (md.item.get("flr_nm") or "").strip()
                return any(f in flr_nm for f in self.known_activist_funds)
            return True

        try:
            # shared primitive — 단일 keyword group(대량보유). flr_nm 의존 filter 는 keep.
            for md in scan_disclosures(
                partial(_boundary.dart_iter_disclosures, api_key),
                bgn_de=bgn_dt.strftime("%Y-%m-%d"),
                end_de=ctx.date,
                pblntf_ty="D",
                keyword_groups={"activist_5pct_filing": ("주식등의대량보유상황",)},
                keep=_keep,
                dedup_key=lambda md: f"DART-{md.rcept_dt}-{md.rcept_no}-activist",
            ):
                flr_nm = (md.item.get("flr_nm") or "").strip()
                out.append(
                    CatalystEvent(
                        catalyst_id=f"DART-{md.rcept_dt}-{md.rcept_no}-activist",
                        ticker=md.ticker,
                        name=ctx.universe[md.ticker],
                        catalyst_type="activist_5pct_filing",
                        trigger_class="d_type",
                        detected_at=ctx.fetched_at,
                        source_citation=_boundary.format_citation(
                            "DART", md.rcept_dt, {"rcept_no": md.rcept_no, "filer": flr_nm}
                        ),
                        metadata={
                            "report_nm": md.report_nm,
                            "filer_name": flr_nm,
                            "augment_only_note": _AUGMENT_NOTE,
                        },
                    )
                )
        except _boundary.DartUnavailable as exc:
            warnings.append(f"activist_5pct_filing error: {exc}")
        return DetectResult(tuple(out), tuple(warnings))
