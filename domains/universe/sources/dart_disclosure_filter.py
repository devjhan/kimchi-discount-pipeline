"""DartDisclosureFilter — DART 공시 list 를 keyword 매칭으로 필터링하는 generic source.

*Pain 1 / 2 정면 해결* — 원래 ``domains/alpha_factory/universe.py`` 의 다음 3 함수
가 35-60줄씩 동일 retry 로직을 복제하던 것을 단일 클래스로 통합:

- ``discover_treasury_actions`` (L202-300) → instance: name="treasury_action"
- ``discover_spin_off_announcements`` (L303-392) → instance: name="spin_off_or_merger"
- ``discover_activist_filings`` (L395-492) → instance: name="activist_filing"

3 인스턴스의 차이점 (pblntf_ty / keyword_groups / source_category / annotate_filers /
priority_groups) 은 ``config/sources.yaml`` 에서 주입. 본 클래스는 retry / dedup /
UniverseEntry 빌드 로직 single source — 5/14 incident progressive degrade 패치도
한 곳에서만 갱신.

설계 차이 (legacy → new):
- spin_off / merger 가 별도 source_category 였던 것 → ``spin_off_or_merger`` 단일 카테고리.
  세부 구분은 ``metadata.kind`` 로 보존 (downstream stage 가 필요 시 활용).
- activist 의 "임원ㆍ주요주주특정증권등소유상황" pattern 검사 → 제거 (legacy 코드도
  is_5pct_filing 체크에서 항상 reject 되던 dead code).
- annotate_filers 가 empty 면 metadata 에 ``filer_name`` / ``known_activist`` 미추가.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from functools import partial
from typing import Any, Mapping

from domains.universe import _boundary
from domains.universe.domain.entry import UniverseEntry
from domains.universe.sources.base import DiscoveryContext, DiscoverySource, SourceResult
from domains.universe.sources.registry import register_source
from domains._shared.adapters.disclosure_scan import MatchedDisclosure, scan_disclosures


def _universe_dedup_key(md: MatchedDisclosure) -> str:
    """universe dedup key: ``ticker|rcept_no|matched_group`` (구 _maybe_build_entry 보존)."""
    return f"{md.ticker}|{md.rcept_no}|{md.matched_group}"


def _normalize_keyword_groups(
    raw: Any, name: str
) -> dict[str, tuple[str, ...]]:
    """``keyword_groups`` YAML → ``dict[str, tuple[str, ...]]`` 정규화."""
    if not isinstance(raw, dict):
        raise ValueError(
            f"dart_disclosure_filter '{name}': keyword_groups 는 dict 이어야 함 "
            f"(got: {type(raw).__name__})"
        )
    out: dict[str, tuple[str, ...]] = {}
    for group_name, keywords in raw.items():
        if not isinstance(keywords, (list, tuple)):
            raise ValueError(
                f"dart_disclosure_filter '{name}': keyword_groups[{group_name!r}] "
                f"는 list 이어야 함"
            )
        out[str(group_name)] = tuple(str(k) for k in keywords)
    if not out:
        raise ValueError(
            f"dart_disclosure_filter '{name}': keyword_groups 가 비어 있음"
        )
    return out


@register_source("dart_disclosure_filter")
@dataclass(frozen=True)
class DartDisclosureFilter(DiscoverySource):
    """DART 공시 keyword 필터링 + progressive degrade retry — 3 source 통합 구현."""

    name: str
    pblntf_ty: str
    """DART 공시 type prefix — 'B' (정기공시 등) / 'D' (지분공시) 등."""

    lookback_months: int
    """기본 lookback 개월수. progressive_degrade=True 면 실패 시 절반으로 1회 재시도."""

    keyword_groups: Mapping[str, tuple[str, ...]]
    """{group_name: (keyword, ...)}. report_nm 에 group 의 keyword 가 1개 이상 포함 시 매칭.

    매칭된 group_name 이 UniverseEntry.metadata['kind'] 로 저장.
    """

    source_category: str
    """모든 매칭 entry 의 source_category (group 별로 다르지 않음)."""

    progressive_degrade: bool = True
    """True: 첫 시도 실패 시 lookback 절반으로 1회 재시도, 성공 시 degraded=True."""

    annotate_filers: tuple[str, ...] = ()
    """비어 있지 않으면: metadata 에 ``filer_name`` 추가 + filer 가 본 리스트 항목을
    포함하면 ``known_activist=True`` 추가 (activist_filing 전용 metadata)."""

    priority_groups: Mapping[str, str] = field(default_factory=dict)
    """{group_name: priority_note}. 매칭된 group_name 이 본 dict 의 키면
    metadata 에 ``priority_note=value`` 추가 (treasury_action 의 'cancellation' 전용)."""

    @classmethod
    def from_spec(cls, spec: dict[str, Any]) -> "DartDisclosureFilter":
        name = spec.get("name")
        if not name:
            raise ValueError(f"dart_disclosure_filter: name 필수 (spec={spec})")
        required = ("pblntf_ty", "lookback_months", "keyword_groups", "source_category")
        for k in required:
            if k not in spec:
                raise ValueError(f"dart_disclosure_filter '{name}': '{k}' 필수")
        return cls(
            name=str(name),
            pblntf_ty=str(spec["pblntf_ty"]),
            lookback_months=int(spec["lookback_months"]),
            keyword_groups=_normalize_keyword_groups(spec["keyword_groups"], str(name)),
            source_category=str(spec["source_category"]),
            progressive_degrade=bool(spec.get("progressive_degrade", True)),
            annotate_filers=tuple(str(f) for f in spec.get("annotate_filers", []) or []),
            priority_groups={
                str(k): str(v) for k, v in (spec.get("priority_groups") or {}).items()
            },
        )

    def discover(self, ctx: DiscoveryContext) -> SourceResult:
        env = dict(ctx.env)
        warnings: list[str] = []

        if not _boundary.dart_has_key(env):
            warnings.append(
                f"{self.name}: DART_API_KEY missing → discovery skipped"
            )
            return SourceResult(entries=(), warnings=tuple(warnings), degraded=False)

        api_key = env.get("DART_API_KEY", "").strip()
        end_date = ctx.clock.trading_date
        fetched_at = _boundary.now_iso_kst()
        source = partial(_boundary.dart_iter_disclosures, api_key)

        # progressive degrade attempt list
        attempts: list[int] = [self.lookback_months]
        if self.progressive_degrade:
            half = max(1, self.lookback_months // 2)
            if half != self.lookback_months:
                attempts.append(half)

        entries: list[UniverseEntry] = []
        degraded = False
        last_exc: Exception | None = None

        for attempt_idx, attempt_months in enumerate(attempts):
            entries = []
            bgn_date = end_date - timedelta(days=attempt_months * 31)
            try:
                # shared primitive: iterate → stock_code 검증 → keyword 첫매칭 → dedup
                # (구 _maybe_build_entry 의 검증/dedup 본문). 매핑만 _build_entry 잔류.
                for md in scan_disclosures(
                    source,
                    bgn_de=bgn_date.isoformat(),
                    end_de=end_date.isoformat(),
                    pblntf_ty=self.pblntf_ty,
                    keyword_groups=self.keyword_groups,
                    dedup_key=_universe_dedup_key,
                ):
                    entries.append(self._build_entry(md, fetched_at))
                last_exc = None
                if attempt_idx > 0:
                    degraded = True
                    warnings.append(
                        f"{self.name}: progressive degrade succeeded after retry "
                        f"(lookback {self.lookback_months}mo → {attempt_months}mo)"
                    )
                break
            except _boundary.DartUnavailable as exc:
                last_exc = exc
                warnings.append(
                    f"{self.name} ({attempt_months}mo): discovery error: {exc}"
                )
                continue

        if last_exc is not None:
            warnings.append(
                f"{self.name}: all retry attempts failed → entries empty"
            )

        return SourceResult(
            entries=tuple(entries),
            warnings=tuple(warnings),
            degraded=degraded,
        )

    def _build_entry(self, md: MatchedDisclosure, fetched_at: str) -> UniverseEntry:
        """매칭된 공시(MatchedDisclosure) → UniverseEntry. 검증/dedup 은 scan_disclosures 책임."""
        corp_name = (md.item.get("corp_name") or "").strip()

        metadata: dict[str, Any] = {"kind": md.matched_group}
        if md.matched_group in self.priority_groups:
            metadata["priority_note"] = self.priority_groups[md.matched_group]

        inclusion_reason = f"{md.matched_group} ({md.report_nm})"

        if self.annotate_filers:
            flr_nm = (md.item.get("flr_nm") or "").strip()
            metadata["filer_name"] = flr_nm
            known = any(f in flr_nm for f in self.annotate_filers)
            metadata["known_activist"] = known
            if known:
                inclusion_reason = (
                    f"{md.matched_group} by {flr_nm} [known_activist] ({md.report_nm})"
                )
            elif flr_nm:
                inclusion_reason = f"{md.matched_group} by {flr_nm} ({md.report_nm})"

        return UniverseEntry(
            ticker=md.ticker,
            name=corp_name,
            source_category=self.source_category,
            inclusion_reason=inclusion_reason,
            fetched_at=fetched_at,
            source_citation=_boundary.format_citation(
                "DART", md.rcept_dt or fetched_at, md.rcept_no or "n/a"
            ),
            metadata=metadata,
        )
