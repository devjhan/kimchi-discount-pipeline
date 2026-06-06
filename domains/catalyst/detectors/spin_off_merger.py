"""spin_off_or_merger detector — 분할/합병 (a_type primary).

구 ``catalyst_scan.detect_spin_off_or_merger`` 이전. catalyst_type 은 매치 키워드에
따라 ``spin_off_announcement`` 또는 ``merger_announcement``.
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

_KEYWORDS = (
    ("spin_off_announcement", ("분할결정", "회사분할", "인적분할", "물적분할")),
    ("merger_announcement", ("합병결정", "합병계약", "분할합병결정")),
)


@register_detector("spin_off_or_merger")
@dataclass(frozen=True)
class SpinOffMergerDetector(CatalystDetector):
    name: str
    enabled: bool
    spin_off_lookback_days: int
    merger_lookback_days: int

    @classmethod
    def from_spec(cls, spec: dict[str, Any]) -> "SpinOffMergerDetector":
        return cls(
            name=str(spec["name"]),
            enabled=bool(spec.get("enabled", True)),
            spin_off_lookback_days=int(spec.get("spin_off_lookback_days", 60)),
            merger_lookback_days=int(spec.get("merger_lookback_days", 60)),
        )

    def detect(self, ctx: DetectContext) -> DetectResult:
        warnings: list[str] = []
        api_key = ctx.env.get("DART_API_KEY", "")
        if not api_key:
            warnings.append("DART_API_KEY missing → spin_off / merger skipped")
            return DetectResult((), tuple(warnings))
        lookback_max = max(self.spin_off_lookback_days, self.merger_lookback_days)
        end_dt = datetime.strptime(ctx.date, "%Y-%m-%d")
        bgn_dt = end_dt - timedelta(days=lookback_max)
        out: list[CatalystEvent] = []
        try:
            # shared primitive — keyword group(spin_off / merger) 첫매칭이 catalyst_type.
            # dict(_KEYWORDS) 는 삽입순 보존 → 구 tuple 순회와 동일 first-match.
            for md in scan_disclosures(
                partial(_boundary.dart_iter_disclosures, api_key),
                bgn_de=bgn_dt.strftime("%Y-%m-%d"),
                end_de=ctx.date,
                pblntf_ty="B",
                keyword_groups=dict(_KEYWORDS),
                keep=lambda md: md.ticker in ctx.universe,
                dedup_key=lambda md: f"DART-{md.rcept_dt}-{md.rcept_no}-{md.matched_group}",
            ):
                out.append(
                    CatalystEvent(
                        catalyst_id=f"DART-{md.rcept_dt}-{md.rcept_no}-{md.matched_group}",
                        ticker=md.ticker,
                        name=ctx.universe[md.ticker],
                        catalyst_type=md.matched_group,
                        trigger_class="a_type",
                        detected_at=ctx.fetched_at,
                        source_citation=_boundary.format_citation(
                            "DART", md.rcept_dt, {"rcept_no": md.rcept_no, "report_nm": md.report_nm}
                        ),
                        metadata={"report_nm": md.report_nm},
                    )
                )
        except _boundary.DartUnavailable as exc:
            warnings.append(f"spin_off / merger error: {exc}")
        return DetectResult(tuple(out), tuple(warnings))
