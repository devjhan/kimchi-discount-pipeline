"""policy CLI entry — out-of-band 정책 producer (sync).

usage:
    python -m domains.policy.main --ticker KR:005930 --trigger filing:rcept_no=2026...
    python -m domains.policy.main --ticker KR:005930            # manual trigger
    python -m domains.policy.main --dry-run                      # intake report only

엔진(LLM) 미주입(기본) 이면 intake-only — trigger 를 draft 로 기록하고 보고만 한다
(Default No-Action). 엔진 주입 시 trigger 별 analyze → commit (profile_registry 신규
버전). 자동 실행 금지 — launchd LaunchAgent 경유 (governance/schedules.yaml).

이 모듈은 universe/screener 의 daily batch 와 분리된 자체 일정으로 돈다. consumer 는
registry 만 소비하며 policy 를 동기 호출하지 않는다.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import date as _date
from datetime import datetime
from pathlib import Path
from typing import Any

from domains._shared.profile_registry.errors import ProfileDriftError
from domains._shared.profile_registry.registry import ProfileRegistry
from domains._shared.time.clock import AsOfClock
from domains.policy import _boundary
from domains.policy.application.analyze import run_analysis
from domains.policy.application.commit import commit_profile
from domains.policy.application.intake import build_triggers
from domains.policy.audit.log import ViolationLog
from domains.policy.domain.cutoff_validate import CutoffContractError, make_strict_validator
from domains.policy.domain.research_result import ResearchOutput
from domains.policy.domain.trigger import Trigger
from domains.policy.ports.llm import PolicyEngine

STAGE_NAME = "policy-producer"


def _strict_validator():
    """manifest 기반 strict cutoff validator (composition root 주입; ADR-0014, findings 2/3).

    policy 는 manifest 를 DATA 로만 읽는다 (bc-independent — screener 내부 import 없음).
    commit_profile 의 기본은 shape-only 라 순수 도메인 테스트는 불변; 본 진입점만 strict.
    """
    return make_strict_validator(_boundary.methods_manifest())
_DEFAULT_DRIFT_THRESHOLD = 0.5


def _parse_date(s: str | None) -> _date:
    if s:
        return datetime.strptime(s, "%Y-%m-%d").date()
    return _boundary.now_kst().date()


def _ticker_dir(ticker: str) -> str:
    return ticker.replace(":", "_")


def _kind_of(trigger: str | None) -> str:
    """"filing:rcept_no=..." → "filing"; "news:..." → "news"; 그 외 → "manual"."""
    if trigger and ":" in trigger:
        return trigger.split(":", 1)[0]
    return "manual"


def _profile_summary(profile: Any) -> dict[str, Any] | None:
    """현 EnrichCutoffProfile 의 amend 컨텍스트 요약 (version + enrich + cutoff_rules)."""
    if profile is None:
        return None
    return {
        "profile_version": profile.profile_version,
        "required_enrichments": list(profile.required_enrichments),
        "cutoff_rules": dict(profile.cutoff_rules),
    }


def _emit_intake(triggers: tuple[Trigger, ...], clock: AsOfClock) -> None:
    """phase 1 (결정론) — trigger + 현 profile 동봉 intake 산출. LLM·commit 없음 (G10).

    ``investment-policy-profiler`` 스킬이 본 intake + ``config/signals/{ticker}/`` evidence
    (ingest-external-signal SOP 의 fact-only redacted 산출)를 읽어 _profile-draft 를 만든다.
    """
    registry = ProfileRegistry(root=_boundary.profiles_root())
    for t in triggers:
        intake = {
            "trigger": asdict(t),
            "current_profile": _profile_summary(registry.load_latest(t.ticker)),
            "evidence_dir_hint": f"config/signals/{_ticker_dir(t.ticker)}/",
            "note": (
                "investment-policy-profiler 스킬이 본 intake + evidence 로 _profile-draft "
                "산출. drift/version/commit 은 'python -m domains.policy.main "
                "--commit-draft <draft>' 결정론 (F-10: 스킬은 commit 안 함)."
            ),
        }
        out_path = (
            _boundary.drafts_dir()
            / _ticker_dir(t.ticker)
            / f"_intake-{clock.trading_date.isoformat()}.json"
        )
        _boundary.write_output_safely(out_path, intake)


def _commit_from_draft(path: str, clock: AsOfClock, *, drift_threshold: float) -> int:
    """phase 3 (결정론) — 스킬 산출 profile-draft JSON → ResearchOutput → commit.

    drift/version/provenance/G20 + ``validate_rules``(shape) 는 ``commit_profile`` 결정론.
    스킬은 본 단계를 수행하지 않는다 (F-10 불변식 — LLM 은 commit 안 함, 환각 차단).
    """
    p = Path(path)
    if not p.exists():
        print(f"[{STAGE_NAME}] commit-draft: {path} 미존재", file=sys.stderr)
        return 2
    raw = json.loads(p.read_text(encoding="utf-8"))
    payload = raw.get("payload", raw) if isinstance(raw, dict) else {}
    try:
        out = ResearchOutput(
            ticker=str(payload["ticker"]),
            required_enrichments=tuple(payload.get("required_enrichments") or ()),
            cutoff_rules=dict(payload.get("cutoff_rules") or {}),
            citations=tuple(payload.get("citations") or ()),
            rationale_ko=str(payload.get("rationale_ko") or ""),
        )
    except (KeyError, TypeError) as exc:
        print(f"[{STAGE_NAME}] commit-draft: 불량 draft schema — {exc}", file=sys.stderr)
        return 2
    registry = ProfileRegistry(root=_boundary.profiles_root())
    audit_log = ViolationLog(clock)
    try:
        result = commit_profile(
            out,
            registry,
            writer=_boundary.write_profile_safely,
            audit_log=audit_log,
            drift_threshold=drift_threshold,
            validate_rules=_strict_validator(),
            trigger=str(payload.get("trigger") or "skill-draft"),
        )
    except ProfileDriftError as exc:
        print(f"[{STAGE_NAME}] commit-draft blocked (drift): {exc}", file=sys.stderr)
        return 2
    except CutoffContractError as exc:
        print(
            f"[{STAGE_NAME}] commit-draft blocked (cutoff contract): {exc}",
            file=sys.stderr,
        )
        return 2
    print(
        f"[{STAGE_NAME}] committed {out.ticker} v{result.version} "
        f"(drift Δ{result.drift.max_threshold_delta:.2f}) → {result.path}"
    )
    return 2 if audit_log.has_blocking else 0


def main(argv: list[str] | None = None, *, engine: PolicyEngine | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="domains.policy.main",
        description="정책 producer — trigger → research → profile commit (out-of-band).",
    )
    parser.add_argument("--ticker", help="KR:NNNNNN — 정책 검토 대상 종목.")
    parser.add_argument("--trigger", help='"filing:rcept_no=..." | "news:..." | "manual".')
    parser.add_argument("--date", help="YYYY-MM-DD (KST). 기본: 오늘 거래일.")
    parser.add_argument(
        "--drift-threshold",
        type=float,
        default=_DEFAULT_DRIFT_THRESHOLD,
        help=f"threshold 상대 변동 한계 (기본 {_DEFAULT_DRIFT_THRESHOLD}). 초과 시 audit warning.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="intake report only — analyze/commit skip.",
    )
    parser.add_argument(
        "--commit-draft",
        help="스킬(investment-policy-profiler) 산출 profile-draft JSON 경로 → 결정론 "
        "commit (drift/version/provenance/G20). intake/LLM 없이 phase 3 만 수행.",
    )
    args = parser.parse_args(argv)

    clock = AsOfClock.at_market_close(_parse_date(args.date))
    now_iso = _boundary.now_iso_kst()

    # ----- phase 3: commit-draft (스킬 산출 profile-draft → 결정론 commit) -----
    if args.commit_draft:
        return _commit_from_draft(
            args.commit_draft, clock, drift_threshold=args.drift_threshold
        )

    # ----- intake (순수) — CLI manual trigger. DART scan 은 engine 연동 시 확장. -----
    events = []
    if args.ticker:
        events.append(
            {
                "kind": _kind_of(args.trigger),
                "ticker": args.ticker,
                "payload_ref": args.trigger or "manual",
            }
        )
    triggers = build_triggers(events, now_iso=now_iso)

    if not triggers:
        print(f"[{STAGE_NAME}] no triggers — Default No-Action")
        return 0

    # ----- intake-only (엔진 미주입 / dry-run) — phase 1 (스킬 input 산출) -----
    if engine is None or args.dry_run:
        _emit_intake(triggers, clock)
        mode = "dry-run" if args.dry_run else "no-engine"
        print(
            f"[{STAGE_NAME}] intake-only ({mode}): {len(triggers)} trigger(s) "
            f"→ _intake drafts. analyze/commit skip "
            f"(investment-policy-profiler 스킬 → --commit-draft 대기)."
        )
        return 0

    # ----- analyze + commit (engine 주입 시) -----
    registry = ProfileRegistry(root=_boundary.profiles_root())
    audit_log = ViolationLog(clock)
    for t in triggers:
        out = run_analysis(t, engine, evidence=())
        draft = _boundary.drafts_dir() / _ticker_dir(t.ticker) / f"_profile-draft-{clock.trading_date.isoformat()}.json"
        _boundary.write_output_safely(
            draft,
            {
                "ticker": out.ticker,
                "required_enrichments": list(out.required_enrichments),
                "cutoff_rules": dict(out.cutoff_rules),
                "citations": list(out.citations),
                "rationale_ko": out.rationale_ko,
            },
        )
        result = commit_profile(
            out,
            registry,
            writer=_boundary.write_profile_safely,
            audit_log=audit_log,
            drift_threshold=args.drift_threshold,
            validate_rules=_strict_validator(),
            trigger=t.describe(),
        )
        print(
            f"[{STAGE_NAME}] committed {out.ticker} v{result.version} "
            f"(drift Δ{result.drift.max_threshold_delta:.2f}) → {result.path}"
        )

    return 2 if audit_log.has_blocking else 0


if __name__ == "__main__":
    sys.exit(main())
