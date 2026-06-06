"""treasury_share_cancellation detector — 자사주 소각 (a_type primary).

구 ``catalyst_scan.detect_treasury_cancellation`` 이전. DART pblntf_ty='B' 키워드 매치.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import partial
from typing import Any

from domains.catalyst import _boundary
from domains.catalyst.detectors.base import CatalystDetector, DetectContext, DetectResult
from domains.catalyst.detectors.registry import register_detector
from domains.catalyst.domain.event import CatalystEvent
from domains._shared.adapters.disclosure_scan import scan_disclosures

_KEYWORDS = ("주식소각", "자기주식소각", "이익소각")


@register_detector("treasury_share_cancellation")
@dataclass(frozen=True)
class TreasuryCancellationDetector(CatalystDetector):
    name: str
    enabled: bool
    lookback_days: int

    @classmethod
    def from_spec(cls, spec: dict[str, Any]) -> "TreasuryCancellationDetector":
        return cls(
            name=str(spec["name"]),
            enabled=bool(spec.get("enabled", True)),
            lookback_days=int(spec.get("lookback_days", 30)),
        )

    def detect(self, ctx: DetectContext) -> DetectResult:
        warnings: list[str] = []
        api_key = ctx.env.get("DART_API_KEY", "")
        if not api_key:
            warnings.append("DART_API_KEY missing → treasury_share_cancellation skipped")
            return DetectResult((), tuple(warnings))
        end_dt = datetime.strptime(ctx.date, "%Y-%m-%d")
        bgn_dt = end_dt - timedelta(days=self.lookback_days)
        out: list[CatalystEvent] = []
        try:
            # shared primitive — stock_code 검증 + keyword 매칭 + dedup. G14 universe
            # 게이트는 keep 으로 주입 (dedup 전, 구 inline 순서와 byte-동일).
            for md in scan_disclosures(
                partial(_boundary.dart_iter_disclosures, api_key),
                bgn_de=bgn_dt.strftime("%Y-%m-%d"),
                end_de=ctx.date,
                pblntf_ty="B",
                keyword_groups={"treasury_share_cancellation": _KEYWORDS},
                keep=lambda md: md.ticker in ctx.universe,
                dedup_key=lambda md: f"DART-{md.rcept_dt}-{md.rcept_no}",
            ):
                out.append(
                    CatalystEvent(
                        catalyst_id=f"DART-{md.rcept_dt}-{md.rcept_no}",
                        ticker=md.ticker,
                        name=ctx.universe[md.ticker],
                        catalyst_type="treasury_share_cancellation",
                        trigger_class="a_type",
                        detected_at=ctx.fetched_at,
                        source_citation=_boundary.format_citation(
                            "DART", md.rcept_dt, {"rcept_no": md.rcept_no, "report_nm": md.report_nm}
                        ),
                        metadata={"lookback_days": self.lookback_days, "report_nm": md.report_nm},
                    )
                )
        except _boundary.DartUnavailable as exc:
            warnings.append(f"treasury_share_cancellation error: {exc}")
        return DetectResult(tuple(out), tuple(warnings))
