"""universe CLI entry — Stage 1 universe build.

usage:
    python -m domains.universe.main --date 2026-05-17
    python -m domains.universe.main --dry-run
    python -m domains.universe.main --trail-dir /custom/dir

audit wiring:
- source from_spec 검증 실패 → GuardViolation(severity='blocking') + exit 2
- ViolationLog 의 has_blocking 이 exit code 결정

산출물: ``$TRAIL_TODAY/01-universe.json`` (envelope schema ``investment-stage1-universe-v1``)
- 본 schema 는 legacy ``domains.alpha_factory.universe`` 와 호환 — downstream
  (stage1_nav_calc / stage1_pref_spread / screener / catalyst_scan) 이 본 schema
  의 ``entries[].source_category`` / ``entries[].ticker`` / ``entries[].name`` read.
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import asdict
from datetime import date as _date
from datetime import datetime
from pathlib import Path
from typing import Callable

from domains._shared.profile_registry.registry import ProfileRegistry
from domains._shared.segment_registry.concepts import ConceptRegistry
from domains._shared.segment_registry.errors import SegmentRegistryError
from domains._shared.segment_registry.registry import (
    SegmentProfileRegistry,
    SegmentRegistry,
)
from domains._shared.segment_registry.resolver import SegmentResolver
from domains._shared.segment_registry.schema import PolicyContribution
from domains._shared.time.clock import AsOfClock
from domains.universe import _boundary
from domains.universe.application.build_universe import build_universe
from domains.universe.audit.invariants import (
    validate_enricher_applies_to,
    validate_g7_citations,
)
from domains.universe.audit.log import ViolationLog
from domains.universe.audit.violation import GuardViolation
from domains.universe.enrichers.factory import build_enrichers
from domains.universe.sources.factory import build_sources

SCHEMA_VERSION = "investment-stage1-universe-v1"
STAGE_NAME = "stage1-universe"
_SOURCES_CONFIG_FILENAME = "sources.yaml"
_EXCLUSIONS_CONFIG_FILENAME = "exclusions.yaml"
_ENRICHERS_CONFIG_FILENAME = "enrichers.yaml"


def _parse_date(s: str | None) -> _date:
    """``YYYY-MM-DD`` 또는 None. None 이면 KST 오늘 거래일."""
    if s:
        return datetime.strptime(s, "%Y-%m-%d").date()
    return _boundary.now_kst().date()


def _build_segment_resolver(
    *, default_contribution: PolicyContribution | None = None
) -> SegmentResolver | None:
    """segment 해소기 구성 (boundary→registries→resolver). 실패 시 None.

    per-ticker profile 은 ProfileRegistry 로 resolver 가 fold(union). ``default_contribution``
    은 ADR-0013 decision 4 의 global=root segment seam — universe 는 *required_enrichments*
    만 union 하는데, whole-universe global *enrichment* 산출물은 존재하지 않는다(global
    정책 quality_floor 의 required_enrichments=[] — global scope 는 screener cutoff 전용,
    decision 3). 따라서 caller 는 현재 None 을 주입한다(global enrichment base 부재).
    cutoff 측 global=root segment 는 screener 가 주입한다. 구성 단계 실패
    (segment 순환 / 손상 segment·concept 파일 / 인덱스 IO)는 SegmentRegistryError 또는
    OSError 로 잡아 None 반환 → caller 가 segment 비활성으로 graceful fallback.
    """
    try:
        seg_registry = SegmentRegistry(root=_boundary.segments_root())
        concept_registry = ConceptRegistry(root=_boundary.concepts_root())
        named_registry = SegmentProfileRegistry(root=_boundary.segment_profiles_root())
        per_ticker_registry = ProfileRegistry(root=_boundary.profiles_root())
        return SegmentResolver(
            segments=seg_registry.load_all_latest(),
            known_concepts=frozenset(concept_registry.list_concepts()),
            vector_index=_boundary.vector_index(),
            named_profile_for=named_registry.load_latest,
            per_ticker_for=per_ticker_registry.load_latest,
            default_contribution=default_contribution,
            now_iso=_boundary.now_iso_kst,
        )
    except (SegmentRegistryError, OSError):
        return None


def _emit_runtime_invariant_violations(
    *,
    result_entries: tuple,  # tuple[EnrichedEntry, ...]
    sources: list,
    enrichers: list,
    violation_log: ViolationLog,
) -> None:
    """G7 citation 검증 + enricher applies_to 일관성 검사 후 violation_log 에 기록.

    severity:
    - G7 malformed citation → ``warning`` (run 자체는 진행)
    - orphan enricher (applies_to 가 source_categories 와 disjoint) → ``warning``
    """
    # G7: per-entry citation 형식
    g7_violations = validate_g7_citations(result_entries)
    for v in g7_violations:
        violation_log.record(
            GuardViolation(
                detected_at=_boundary.now_kst(),
                severity="warning",
                rule_name="g7_citation_format",
                ticker=v.ticker,
                message=f"malformed citations: {list(v.bad_citations)}",
                context={"source_category": v.source_category},
            )
        )

    # source_category consistency: orphan enricher (runtime — dead code 탐지)
    # 외부 감사 fix 2026-05-17: static config (sources 의 declared source_category)
    # 대신 *runtime entries* 의 source_category 로 검증. static 검증은 declared
    # 카테고리에 enricher 가 매칭되어도 실제로는 entry 가 emit 안 되는 경우
    # (e.g., DART skip / 데이터 부재) dead code 를 놓침.
    actual_categories = frozenset(e.source_category for e in result_entries)
    enricher_map = {e.name: e.applies_to for e in enrichers}
    orphans = validate_enricher_applies_to(enricher_map, actual_categories)
    for name in orphans:
        violation_log.record(
            GuardViolation(
                detected_at=_boundary.now_kst(),
                severity="warning",
                rule_name="enricher_orphan",
                ticker=None,
                message=(
                    f"enricher '{name}' applies_to ({sorted(enricher_map[name])}) "
                    f"matches no runtime entries (actual categories: {sorted(actual_categories)})"
                ),
                context={
                    "applies_to": sorted(enricher_map[name]),
                    "actual_source_categories": sorted(actual_categories),
                },
            )
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="domains.universe.main",
        description="Stage 1 — Universe build (fan-in DiscoverySource + exclusions).",
    )
    parser.add_argument("--date", help="YYYY-MM-DD (KST). 기본: 오늘 거래일.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="모든 source discovery skip — sources 의 외부 IO 없이 빈 universe 산출.",
    )
    parser.add_argument(
        "--trail-dir",
        default=None,
        help="output trail dir override. 기본: $TRAIL_TODAY env, else operations/{KST 거래일}.",
    )
    parser.add_argument(
        "--allow-yahoo-fallback",
        action="store_true",
        default=None,
        help="KIS 미가용 시 Yahoo 사용 (CLI 명시 시 True override; "
        "미명시 시 config/user/behavior.yaml 결정)",
    )
    parser.add_argument(
        "--use-profile-registry",
        action="store_true",
        help="POLICY MODE cutover 스위치 — 종목별 profile_registry 의 "
        "required_enrichments 로 보강 (기본 OFF = backward-compat applies_to). "
        "policy 가 프로파일을 생산하고 회귀 parity 가 증명된 뒤 활성화.",
    )
    parser.add_argument(
        "--use-segments",
        action="store_true",
        help="segment 계층(부분집합 profile) 해소로 required_enrichments 보강 (기본 OFF). "
        "SegmentResolver 가 매칭 segment + per-ticker(profile_registry) 의 "
        "required_enrichments 를 union 한다. --use-profile-registry 의 상위집합이며 "
        "동시 지정 시 본 플래그가 우선. 벡터 인덱스 미빌드/키 부재 시 graceful degrade.",
    )
    args = parser.parse_args(argv)

    target_date = _parse_date(args.date)
    clock = AsOfClock.at_market_close(target_date)
    date_iso = clock.trading_date.isoformat()

    violation_log = ViolationLog(clock)

    # ----- config 로드 -----
    sources_cfg = _boundary.load_sources_config()
    enrichers_cfg = _boundary.load_enrichers_config()
    exclusions_cfg = _boundary.load_user_config(_EXCLUSIONS_CONFIG_FILENAME)
    exclusion_tickers = exclusions_cfg.get("tickers") or []
    exclusions = frozenset(str(t) for t in exclusion_tickers)

    # ----- sources + enrichers build -----
    try:
        sources = build_sources(sources_cfg.get("sources") or [])
        enrichers = build_enrichers(enrichers_cfg.get("enrichers") or [])
    except ValueError as exc:
        violation_log.record(
            GuardViolation(
                detected_at=_boundary.now_kst(),
                severity="blocking",
                rule_name="config_build",
                ticker=None,
                message=str(exc),
                context={"sources": _SOURCES_CONFIG_FILENAME, "enrichers": _ENRICHERS_CONFIG_FILENAME},
            )
        )
        print(f"[{STAGE_NAME}] config build blocked: {exc}", file=sys.stderr)
        return 2

    # ----- env load (dry-run 시 빈 dict 사용 — source / enricher 의 GuardSkip 분기) -----
    env: dict[str, str] = {} if args.dry_run else _boundary.load_env()
    if not env and not args.dry_run:
        print(
            f"[{STAGE_NAME}] WARN: .env 로드 실패 — DART/KIS fetch skip 됨",
            file=sys.stderr,
        )

    # ----- profile registry closure (POLICY MODE cutover seam) -----
    # 기본 OFF → None → build_universe 의 backward-compat applies_to 분기.
    # --use-profile-registry 시에만 종목별 required_enrichments 로 보강.
    # 미등록 ticker → frozenset() (보강 안 함 — policy 미실행 정상, Default No-Action).
    # 손상 profile → ProfileSchemaError 전파 (fail-open 금지 — main 에서 surface).
    required_enrichments_for: Callable[[str], frozenset[str]] | None = None
    if args.use_profile_registry:
        _profile_registry = ProfileRegistry(root=_boundary.profiles_root())

        def _req_from_profile_registry(ticker: str) -> frozenset[str]:
            profile = _profile_registry.load_latest(ticker)
            if profile is None:
                return frozenset()
            return frozenset(profile.required_enrichments)

        required_enrichments_for = _req_from_profile_registry

    # ----- segment 계층 해소 (Task 11, --use-segments; --use-profile-registry 의 상위집합) -----
    # ON 시 SegmentResolver 가 매칭 segment + per-ticker 를 union 한 required_enrichments 로
    # 위 closure 를 대체한다. segment config 문제(SegmentRegistryError: 순환/손상/merge
    # 충돌/selector 오류)는 frozenset() 으로 graceful degrade (부분집합 보강 생략). 손상
    # per-ticker(ProfileSchemaError)는 기존 --use-profile-registry 와 동일하게 전파(fail-loud).
    # resolver 구성 자체 실패는 stderr warning 후 위 경로로 fallback (segment 비활성).
    if args.use_segments:
        seg_resolver = _build_segment_resolver()
        if seg_resolver is None:
            print(
                f"[{STAGE_NAME}] WARN: segment 해소기 구성 실패 — segment 비활성",
                file=sys.stderr,
            )
        else:

            def _req_from_segments(ticker: str) -> frozenset[str]:
                try:
                    resolution = seg_resolver.resolve(ticker)
                except SegmentRegistryError:
                    return frozenset()  # segment config 문제 → 보강 생략(graceful)
                if resolution.profile is None:
                    return frozenset()
                return frozenset(resolution.profile.required_enrichments)

            required_enrichments_for = _req_from_segments

    # ----- orchestrate -----
    allow_yahoo = _boundary.resolve_allow_yahoo_fallback(args.allow_yahoo_fallback)
    result = build_universe(
        sources=tuple(sources),
        enrichers=tuple(enrichers),
        exclusions=exclusions,
        clock=clock,
        env=env,
        allow_yahoo=allow_yahoo,
        dry_run=args.dry_run,
        required_enrichments_for=required_enrichments_for,
    )

    # ----- envelope build -----
    envelope = _boundary.base_report_envelope(
        schema=SCHEMA_VERSION,
        date=date_iso,
        config_path=str(_boundary.config_path(_SOURCES_CONFIG_FILENAME)),
        config_version=sources_cfg.get("version", "unknown"),
    )
    envelope.update(
        {
            "stats": result.stats,
            "entries": [asdict(e) for e in result.entries],
            "warnings": [_boundary.secret_safe_log(w, env) for w in result.warnings],
            "skipped_sources": [asdict(s) for s in result.skipped_sources],
        }
    )

    # ----- runtime invariants (G7 citation + enricher applies_to consistency) -----
    _emit_runtime_invariant_violations(
        result_entries=result.entries,
        sources=sources,
        enrichers=enrichers,
        violation_log=violation_log,
    )

    # ----- write trail -----
    trail_dir = Path(args.trail_dir) if args.trail_dir else _boundary.resolve_trail_dir(date_iso)
    trail_dir.mkdir(parents=True, exist_ok=True)
    out_path = trail_dir / "01-universe.json"
    final = _boundary.write_output_safely(out_path, envelope)

    # ----- handoff summary -----
    by_cat = result.stats.get("by_source_category") or {}
    summary_categories = ", ".join(f"{k}={v}" for k, v in sorted(by_cat.items())) or "(empty)"
    _boundary.emit_summary(
        STAGE_NAME,
        {
            "date": date_iso,
            "total": result.stats.get("total", 0),
            "excluded": result.stats.get("excluded", 0),
            "categories": f"[{summary_categories}]",
            "warnings": len(result.warnings),
            "mode": "dry-run" if args.dry_run else "live",
        },
        final,
    )

    return 2 if violation_log.has_blocking else 0


if __name__ == "__main__":
    sys.exit(main())