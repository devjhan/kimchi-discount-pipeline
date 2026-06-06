"""screener CLI 진입점.

usage:
    python -m domains.screener.main --date 2026-05-15 --strategy default
    python -m domains.screener.main --dry-run

dry-run 은 DART fetch 없이 cache hit 만 평가. 모든 cache miss = verdict=unknown.
PR3 검증 단계에서 alpha_factory 산출과 verdicts diff = 0 verify.

audit wiring:
- HardGuardViolationError catch → GuardViolation(severity='blocking') + exit 2
- Citation G7 형식 검증 → 위반 시 GuardViolation(severity='warning') 기록
- ViolationLog 의 has_blocking 이 exit code 결정
"""
from __future__ import annotations

import argparse
import sys
from datetime import date as _date
from datetime import datetime
from typing import Any

from domains.screener import _boundary
from domains.screener.application.screen import run_screen, verdicts_as_json
from domains.screener.audit.citation import is_valid_citation
from domains.screener.audit.log import ViolationLog
from domains.screener.audit.violation import GuardViolation
from domains.screener.errors import HardGuardViolationError
from domains.screener.io.financial_cache import (
    LiveFinancialCache,
    policy_from_strategy,
)
from domains.screener.io.trail_writer import write_quality_filter
from domains.screener.io.universe_loader import load_universe
from domains.screener.rules.base import Rule
from domains.screener.rules.factory import RuleFactory
from domains._shared.profile_registry.errors import ProfileSchemaError
from domains._shared.profile_registry.registry import ProfileRegistry
from domains._shared.profile_registry.schema import EnrichCutoffProfile
from domains._shared.time.clock import AsOfClock


def _collect_profile_refs(spec: dict[str, Any]) -> set[str]:
    """rule 트리 YAML 에서 ``profile_ref`` 의 profile 이름 모두 수집.

    nested profile_ref (예: AND(quality_floor, low_psr)) 도 지원.
    main.py 의 profile 로더가 본 함수의 결과로 일괄 로드.
    """
    refs: set[str] = set()
    if not isinstance(spec, dict):
        return refs
    if spec.get("type") == "profile_ref":
        name = spec.get("profile")
        if isinstance(name, str):
            refs.add(name)
    for key in ("children", "inner"):
        v = spec.get(key)
        if isinstance(v, list):
            for c in v:
                if isinstance(c, dict):
                    refs |= _collect_profile_refs(c.get("rule", c))
        elif isinstance(v, dict):
            refs |= _collect_profile_refs(v)
    return refs


def _parse_date(s: str | None) -> _date:
    """``YYYY-MM-DD`` 또는 None. None 이면 KST 오늘 거래일."""
    if s:
        return datetime.strptime(s, "%Y-%m-%d").date()
    return _boundary.now_kst().date()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="domains.screener.main",
        description="Stage 2 quality filter — DDD modular monolith screener",
    )
    parser.add_argument("--date", help="YYYY-MM-DD (KST). 기본: 오늘")
    parser.add_argument(
        "--strategy", default="default",
        help="config/strategies/{name}.yaml 의 name (기본: default)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="DART fetch skip. cache miss 인 종목은 verdict=unknown",
    )
    args = parser.parse_args(argv)

    target_date = _parse_date(args.date)
    clock = AsOfClock.at_market_close(target_date)
    date_iso = clock.trading_date.isoformat()

    # ----- config 로드 -----
    strategy = _boundary.load_strategy(args.strategy)
    hard_guards = _boundary.load_hard_guards()
    profile_refs = _collect_profile_refs(strategy["rule"])
    profiles: dict[str, dict] = {
        name: _boundary.load_profile(name) for name in profile_refs
    }

    constants = strategy.get("constants") or {}
    tax_rate = float(constants.get("tax_rate", 0.22))

    # ----- audit / violation log -----
    violation_log = ViolationLog(clock)

    # ----- env / DART key / corp_index -----
    env = _boundary.load_env()
    has_dart = _boundary.dart_has_key(env)
    dart_api_key = env.get("DART_API_KEY") if has_dart else None

    warnings: list[str] = []
    corp_index: dict[str, str] = {}
    if not has_dart and not args.dry_run:
        warnings.append(
            "DART_API_KEY missing — fetch 불가. 모든 cache miss 종목 verdict=unknown."
        )
    if has_dart and not args.dry_run:
        try:
            corp_index_path = _boundary.resolve_path("dart_cache") / "corp_index.json"
            corp_index = _boundary.dart_load_corp_index(
                dart_api_key or "", corp_index_path
            )
        except _boundary.DartUnavailable as exc:
            warnings.append(
                _boundary.secret_safe_log(
                    f"corp_index 로드 실패: {exc}", env
                )
            )

    # ----- universe -----
    universe, uni_warns = load_universe(clock)
    for w in uni_warns:
        warnings.append(_boundary.secret_safe_log(w, env))

    # ----- 전환기 default Rule 트리 (프로파일 없는 종목 fallback) -----
    # invariant 위반은 blocking violation 으로 기록. per-ticker 프로파일 룰의
    # build 실패는 caution 으로 degrade (rule_for closure) — 여기는 default 전략의
    # config 오류만 blocking.
    try:
        default_rule = RuleFactory.build_strategy(
            strategy, profiles, hard_guards, tax_rate=tax_rate
        )
    except HardGuardViolationError as exc:
        violation_log.record(
            GuardViolation(
                detected_at=_boundary.now_kst(),
                severity="blocking",
                rule_name="strategy_build",
                ticker=None,
                message=str(exc),
                context={"strategy": args.strategy},
            )
        )
        warnings.append(f"strategy build blocked: {exc}")
        _boundary.emit_summary(
            "stage2-screener",
            summary={
                "date": date_iso,
                "strategy": args.strategy,
                "mode": "blocked",
                "violation": "hard_guard_override",
            },
            out_path=_boundary.resolve_path("trail_today", date=date_iso)
            / "02-quality-filter.blocked.json",
        )
        return 2

    # ----- profile registry closures (정책/메커니즘 분리) -----
    # 빈 registry (현재 — policy 미실행) → 전 종목 default_rule → 오늘 동작 동일.
    # 손상 프로파일은 per-ticker caution 으로 격리 (배치 미중단 + fail-open 금지).
    registry = ProfileRegistry(root=_boundary.profiles_root())
    _load_cache: dict[str, tuple[EnrichCutoffProfile | None, bool]] = {}
    _rule_cache: dict[tuple[str, int], Rule | None] = {}

    def _load(ticker: str) -> tuple[EnrichCutoffProfile | None, bool]:
        """(profile|None, corrupt). corrupt=True 면 손상 YAML — caution 으로 degrade."""
        if ticker not in _load_cache:
            try:
                _load_cache[ticker] = (registry.load_latest(ticker), False)
            except ProfileSchemaError as exc:
                warnings.append(f"{ticker}: 손상 프로파일 — {exc}")
                _load_cache[ticker] = (None, True)
        return _load_cache[ticker]

    def rule_for(ticker: str) -> Rule | None:
        profile, corrupt = _load(ticker)
        if corrupt:
            return None  # 손상 → caution(invalid_profile_rules), default fallback 아님
        if profile is None:
            return default_rule  # 전환 안전망: 프로파일 없음 → 기존 default
        key = (ticker, profile.profile_version)
        if key not in _rule_cache:
            try:
                strat = {"name": f"profile[{ticker}]", "rule": dict(profile.cutoff_rules)}
                _rule_cache[key] = RuleFactory.build_strategy(
                    strat, {}, hard_guards, tax_rate=tax_rate
                )
            except (ValueError, HardGuardViolationError):
                _rule_cache[key] = None  # 불량 cutoff_rules → caution
        return _rule_cache[key]

    def profile_for(ticker: str) -> EnrichCutoffProfile | None:
        profile, corrupt = _load(ticker)
        return None if corrupt else profile

    # ----- run -----
    cache_dir = _boundary.resolve_path("financials_cache")
    policy = policy_from_strategy(strategy)
    cache = LiveFinancialCache(base_dir=cache_dir, policy=policy)

    # composition root: _boundary 로 어댑터 구성 → 순수 use-case 에 주입 (Phase 0 seam).
    result = run_screen(
        rule_for=rule_for,
        profile_for=profile_for,
        universe=universe,
        cache=cache,
        clock=clock,
        tax_rate=tax_rate,
        dart_api_key=dart_api_key,
        corp_index=corp_index,
        citation=_boundary.citation_adapter(),
        dry_run=args.dry_run,
    )
    warnings.extend(result.warnings)

    # ----- G7 citation 검증 — verdict != unknown 인 종목 한정 -----
    for v in result.verdicts:
        if v.verdict == "unknown":
            continue
        bad = [c for c in v.citations if not is_valid_citation(c)]
        if bad:
            violation_log.record(
                GuardViolation(
                    detected_at=_boundary.now_kst(),
                    severity="warning",
                    rule_name="g7_citation_format",
                    ticker=v.ticker,
                    message=f"malformed citations: {bad}",
                    context={"verdict": v.verdict, "count": len(bad)},
                )
            )

    # ----- 산출 -----
    # dry-run 산출은 alpha_factory production 산출을 덮어쓰지 않도록 별도 filename.
    # PR3 verification: 1주 dry-run 운영하며 양쪽 diff 0 verify 후 PR4 cutover.
    output_meta = strategy.get("output") or {}
    default_filename = output_meta.get(
        "trail_filename", "02-quality-filter.json"
    )
    filename = (
        f"02-quality-filter.screener-dryrun.json" if args.dry_run else default_filename
    )
    out_path = write_quality_filter(
        clock,
        result.verdicts,
        config_path=_boundary.strategy_path(args.strategy),
        config_version=strategy.get("version"),
        warnings=warnings,
        filename=filename,
    )

    # 사이드 채널 — D-Q-6 handoff
    _boundary.emit_summary(
        "stage2-screener",
        summary={
            "date": date_iso,
            "strategy": args.strategy,
            "mode": "dry-run" if args.dry_run else "live",
            **result.stats,
        },
        out_path=out_path,
    )

    # verdicts_as_json 은 PR4+ 의 audit 산출 (별도 file) 에서 사용 예정.
    _ = verdicts_as_json(result.verdicts)
    return 2 if violation_log.has_blocking else 0


if __name__ == "__main__":
    sys.exit(main())
