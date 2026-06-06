"""commit gate — policy 의 진짜 domain 룰 (DDD 역전 해소, F-4 part1).

이전엔 버전 발급 / drift 차단판정 / provenance 조립이 ``application/commit.py`` 에
묻혀 있었고 ``domain/`` 은 빈혈 DTO(Trigger/ResearchOutput)만 들었다. 본 모듈이
그 도메인 룰을 소유한다:

- ``next_version`` — ticker 별 monotonic 버전 발급.
- ``rule_on_drift`` — drift 가 임계를 넘었는가 + (cutover 시) 차단하는가.
- ``assemble_profile`` — provenance 조립 + EnrichCutoffProfile 생성.
- ``decide_commit`` — 위 셋을 한 도메인 판정(``CommitDecision``)으로.

순수 도메인 — I/O / clock 없음. ``committed_at`` 은 application 이 주입(``_boundary``
의 clock 은 application 책임). ``application/commit`` 은 이 판정을 받아 audit 기록 +
``registry`` write 로 **오케스트레이션만** 한다.

차단/경고 의미 확정(F-4 part2)은 cutover(PR7)에서 ``DRIFT_BLOCKS_COMMIT`` 플래그
한 곳을 뒤집어 처리한다 — 현재는 advisory(False), 행동 불변.
"""
from __future__ import annotations

from dataclasses import dataclass

from domains.policy.domain.drift import Drift, compute_drift
from domains.policy.domain.research_result import ResearchOutput
from domains._shared.profile_registry.schema import (
    SCHEMA_VERSION,
    EnrichCutoffProfile,
    Provenance,
)

DRIFT_BLOCKS_COMMIT = False
"""drift 임계 초과 시 commit 을 차단하는가.

현재 advisory(False) — 초과해도 warning audit 만 남기고 commit 진행. cutover(F-4
part2)에서 True 로 전환하면 application 이 ``ProfileDriftError`` raise(hard block).
이 한 줄이 차단/경고 의미의 단일 결정 지점."""


@dataclass(frozen=True)
class DriftRuling:
    """drift 판정 — 임계 초과 여부 + 차단 정책 적용 결과."""

    drift: Drift
    exceeds_threshold: bool
    """prev 존재 + max_threshold_delta > drift_threshold."""
    blocks_commit: bool
    """exceeds_threshold AND DRIFT_BLOCKS_COMMIT. True 면 application 이 차단."""


@dataclass(frozen=True)
class CommitDecision:
    """commit gate 도메인 판정 — 발급 버전 + drift ruling + 조립된 profile."""

    version: int
    ruling: DriftRuling
    profile: EnrichCutoffProfile


def next_version(prev: EnrichCutoffProfile | None) -> int:
    """ticker 별 monotonic 버전 발급. 최초 commit → 1."""
    return (prev.profile_version + 1) if prev else 1


def rule_on_drift(
    prev: EnrichCutoffProfile | None,
    out: ResearchOutput,
    *,
    drift_threshold: float,
) -> DriftRuling:
    """prev 대비 drift 계산 + 임계 초과/차단 판정."""
    drift = compute_drift(prev, out.required_enrichments, out.cutoff_rules)
    exceeds = bool(prev) and drift.max_threshold_delta > drift_threshold
    return DriftRuling(
        drift=drift,
        exceeds_threshold=exceeds,
        blocks_commit=exceeds and DRIFT_BLOCKS_COMMIT,
    )


def assemble_profile(
    out: ResearchOutput,
    *,
    version: int,
    committed_at: str,
    trigger: str,
) -> EnrichCutoffProfile:
    """ResearchOutput → 버전·provenance 박힌 EnrichCutoffProfile (shape 검증은 __post_init__)."""
    return EnrichCutoffProfile(
        ticker=out.ticker,
        schema_version=SCHEMA_VERSION,
        profile_version=version,
        required_enrichments=out.required_enrichments,
        cutoff_rules=out.cutoff_rules,
        description=out.rationale_ko,
        provenance=Provenance(
            committed_at=committed_at,
            committed_by="policy",
            trigger=trigger,
            citations=out.citations,
            rationale_ko=out.rationale_ko,
        ),
    )


def decide_commit(
    prev: EnrichCutoffProfile | None,
    out: ResearchOutput,
    *,
    drift_threshold: float,
    committed_at: str,
    trigger: str,
) -> CommitDecision:
    """버전 발급 + drift 판정 + profile 조립을 한 도메인 판정으로 묶는다."""
    version = next_version(prev)
    ruling = rule_on_drift(prev, out, drift_threshold=drift_threshold)
    profile = assemble_profile(
        out, version=version, committed_at=committed_at, trigger=trigger
    )
    return CommitDecision(version=version, ruling=ruling, profile=profile)
