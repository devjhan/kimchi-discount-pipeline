"""commit — ResearchOutput → (domain commit gate) → profile_registry write 오케스트레이션.

도메인 룰(버전 발급 / drift 차단판정 / provenance 조립)은 ``domain/commit_gate`` 가
소유한다 (F-4 part1, DDD 역전 해소). 본 모듈은 그 판정을 받아 (a) audit 기록 +
(b) registry write 로 **오케스트레이션만** 한다.

NOTE (cross-boundary): ``RuleFactory`` 는 screener internal. policy 가 직접 import
하면 도메인 간 reach. 따라서 ``validate_rules`` 는 **주입 함수** (shape-only). 전체
룰 합법성(metric_path / op / guard-name 충돌)은 screener 로드 시점(Step 4.1 C)에서
잡히며, 불량 프로파일은 caution/fail 로 degrade 될 뿐 silent pass 불가 (hard guard
floor). 기본 validator(``shape_validate_cutoff_rules``)는 'type' 키 존재만 검사.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

from domains.policy import _boundary
from domains.policy.audit.violation import GuardViolation
from domains.policy.domain.commit_gate import decide_commit
from domains.policy.domain.drift import Drift
from domains.policy.domain.research_result import ResearchOutput
from domains._shared.profile_registry.errors import ProfileDriftError
from domains._shared.profile_registry.registry import ProfileRegistry


@dataclass(frozen=True)
class CommitResult:
    path: Path
    drift: Drift
    version: int


def shape_validate_cutoff_rules(cutoff_rules: Any) -> None:
    """shape-only 검증 — Mapping + 'type' 키. 룰 의미는 screener RuleFactory 단독 권위."""
    if not isinstance(cutoff_rules, Mapping) or "type" not in cutoff_rules:
        raise ValueError("cutoff_rules는 'type' 키를 가진 Rule dict-tree여야 함")


def commit_profile(
    out: ResearchOutput,
    registry: ProfileRegistry,
    *,
    writer: Callable[[Path, Any], Path],
    audit_log: Any,
    drift_threshold: float,
    validate_rules: Callable[[Any], None] = shape_validate_cutoff_rules,
    trigger: str = "manual",
) -> CommitResult:
    """ResearchOutput 을 EnrichCutoffProfile 신규 버전으로 commit.

    drift > drift_threshold 면 audit 기록 (severity 는 차단 정책 따라 warning/blocking).
    현재 advisory(commit_gate.DRIFT_BLOCKS_COMMIT=False) — 기록 후 commit 진행. 차단
    모드(cutover) 에선 ProfileDriftError raise. 신규 버전 파일은 덮어쓰기 없이 이력
    보존 (G20).
    """
    # 1. cutoff_rules shape 합법성 (주입 validator — screener internal import 회피).
    validate_rules(out.cutoff_rules)
    # 2. 이전 최신 로드 (clock 은 application 책임 — domain 은 순수 유지).
    prev = registry.load_latest(out.ticker)
    # 3. 도메인 판정 — 버전 + drift ruling + 조립된 profile.
    decision = decide_commit(
        prev,
        out,
        drift_threshold=drift_threshold,
        committed_at=_boundary.now_iso_kst(),
        trigger=trigger,
    )
    ruling = decision.ruling
    # 4. drift 임계 초과 → audit (silent overwrite 금지). 차단 모드면 raise.
    if ruling.exceeds_threshold:
        audit_log.record(
            GuardViolation(
                detected_at=_boundary.now_kst(),
                severity="blocking" if ruling.blocks_commit else "warning",
                rule_name="profile_drift",
                ticker=out.ticker,
                message=f"Δ{ruling.drift.max_threshold_delta:.2f} > {drift_threshold}",
                context={
                    "max_threshold_delta": ruling.drift.max_threshold_delta,
                    "drift_threshold": drift_threshold,
                    "changed_thresholds": dict(ruling.drift.changed_thresholds),
                },
            )
        )
        if ruling.blocks_commit:
            raise ProfileDriftError(
                f"{out.ticker} drift Δ{ruling.drift.max_threshold_delta:.2f} "
                f"> {drift_threshold} (hard block)"
            )
    # 5. commit — 신규 버전 파일 (덮어쓰기 없음; G20).
    path = registry.commit(decision.profile, writer=writer)
    return CommitResult(path=path, drift=ruling.drift, version=decision.version)
