"""index_deletion detector — 지수 편입제외 forced selling (b_type primary).

구 ``catalyst_scan.detect_index_deletion`` (파일 read) + ``stage3_index_deletion_fetch``
(DART fetch) 를 합쳐 in-memory 로 처리 — 중간 ``03-index-deletion.json`` 제거.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from domains.catalyst import _boundary
from domains.catalyst.detectors.base import CatalystDetector, DetectContext, DetectResult
from domains.catalyst.domain.event import CatalystEvent
from domains.catalyst.detectors.registry import register_detector
from domains.catalyst.io.index_deletion_fetch import discover_index_deletions


@register_detector("index_deletion")
@dataclass(frozen=True)
class IndexDeletionDetector(CatalystDetector):
    name: str
    enabled: bool
    lookback_days: int

    @classmethod
    def from_spec(cls, spec: dict[str, Any]) -> "IndexDeletionDetector":
        return cls(
            name=str(spec["name"]),
            enabled=bool(spec.get("enabled", True)),
            lookback_days=int(spec.get("lookback_days", 90)),
        )

    def detect(self, ctx: DetectContext) -> DetectResult:
        entries, warnings = discover_index_deletions(
            dict(ctx.env),
            end_date=ctx.date,
            lookback_days=self.lookback_days,
            fetched_at=ctx.fetched_at,
        )
        out: list[CatalystEvent] = []
        seen: set[str] = set()
        for e in entries:
            if e.ticker not in ctx.universe:  # G14
                continue
            cid = f"INDEX-{e.rcept_dt}-{e.rcept_no}"
            if cid in seen:
                continue
            seen.add(cid)
            out.append(
                CatalystEvent(
                    catalyst_id=cid,
                    ticker=e.ticker,
                    name=ctx.universe[e.ticker],
                    catalyst_type="index_deletion",
                    trigger_class="b_type",
                    detected_at=ctx.fetched_at,
                    source_citation=e.source_citation
                    or _boundary.format_citation("DART", e.rcept_dt, {"rcept_no": e.rcept_no}),
                    metadata={
                        "index_name": e.index_name or "unknown_index",
                        "report_nm": e.report_nm,
                        "rcept_no": e.rcept_no,
                        "rcept_dt": e.rcept_dt,
                    },
                )
            )
        return DetectResult(tuple(out), tuple(warnings))
