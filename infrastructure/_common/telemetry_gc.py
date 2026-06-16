"""telemetry retention GC — 분류기 + 스캐너 + planner (순수 로직).

본 모듈은 FS 를 *변경하지 않는다*:
- ``classify(rel)``  : telemetry 루트 기준 상대경로 → ``Classification`` (kind / scope /
  date / collision_n / canonical_rel / verdict).
- ``scan(root)``     : 트리 walk → ``list[Classification]`` (메타 파일 skip).
- ``plan_gc(...)``   : classification 목록 → ``GCPlan{delete, normalize, keep}`` (3단계 로직).

실제 unlink/rename 은 실행기(``applications.telemetry_gc``)가 plan 을 받아 수행한다.

판정 로직(상세):
  1. LEGACY/ORPHAN
     - glob 미매칭 → ORPHAN (생산자 소멸 산출물 / 미등록 신규 산출물).
     - kind.id_validator 실패(예 ticker ``088350`` ∉ ``^KR_\\d+$``) → ORPHAN.
     - kind.producer_module 부재 → LEGACY (등록됐으나 생산자 소멸).
  2. STALE (SNAPSHOT supersession)
     - retention==SNAPSHOT kind 만. (kind, scope) 그룹 내 최신 date 1건 유지, 나머지 삭제.
  3. COLLISION-DUP (.{N} 정규화, 모든 class 공통)
     - 같은 canonical_rel 그룹에서 최신(max collision_n) 1개만 canonical 파일명으로 정규화,
       나머지 삭제. base(collision_n=0) 단독이면 그대로 유지.
  - PERMANENT/STATE/BINARY 는 supersession 안 함(충돌본 정규화만). EPHEMERAL 은 선택적
    age-prune(keep_days).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path, PurePosixPath
from typing import Iterable, Sequence

from infrastructure._common.telemetry_registry import (
    REGISTRY,
    ArtifactKind,
    RetentionClass,
    producer_exists,
)

# ── per-file verdict (pre-planner) ─────────────────────────────────
ORPHAN = "orphan"
LEGACY = "legacy"
CANDIDATE = "candidate"

# scan 시 분류 대상에서 제외하는 메타 파일 (정책상 GC 가 건드리지 않음).
_IGNORE_NAMES = frozenset({".gitkeep", ".gitignore", ".DS_Store", "README.md"})

_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
_COLLISION_RE = re.compile(r"\.(\d+)$")  # Path.stem 끝의 .{N}


@dataclass(frozen=True)
class Classification:
    rel: str                                  # telemetry 루트 기준 posix 상대경로
    kind: str | None                          # ArtifactKind.kind (None = orphan)
    retention_class: RetentionClass | None
    scope: str | None
    date: str | None                          # YYYY-MM-DD or None
    collision_n: int                          # 0 = canonical, >=1 = .{N}
    canonical_rel: str                        # collision suffix 제거한 상대경로
    verdict: str                              # ORPHAN | LEGACY | CANDIDATE
    reason: str = ""


@dataclass
class GCPlan:
    delete: list[str] = field(default_factory=list)            # 삭제할 rel
    normalize: list[tuple[str, str]] = field(default_factory=list)  # (src_rel → dst_rel) rename
    keep: list[str] = field(default_factory=list)              # 유지되는 canonical rel
    orphans: list[str] = field(default_factory=list)           # ORPHAN rel (delete 부분집합)
    legacy: list[str] = field(default_factory=list)            # LEGACY rel (delete 부분집합)
    stale: list[str] = field(default_factory=list)             # SNAPSHOT 초과분 (delete 부분집합)


# ============================================================
# 분류기 (Task 4)
# ============================================================


def _match_kind(rel: str, kinds: Sequence[ArtifactKind]) -> ArtifactKind | None:
    p = PurePosixPath(rel)
    for k in kinds:
        if p.match(k.glob):
            return k
    return None


def _parse_collision(name: str) -> tuple[int, str]:
    """파일명 → (collision_n, canonical_name). G20 suffix = stem + '.{N}' + suffix."""
    pp = PurePosixPath(name)
    suffix = pp.suffix
    stem = pp.stem
    m = _COLLISION_RE.search(stem)
    if m:
        return int(m.group(1)), stem[: m.start()] + suffix
    return 0, name


def _extract_date(name: str) -> str | None:
    m = _DATE_RE.search(name)
    return m.group(0) if m else None


def _extract_scope(canonical_rel: str, kind: ArtifactKind) -> str | None:
    if kind.scope_segment is None:
        return None
    parts = PurePosixPath(canonical_rel).parts
    if kind.scope_segment >= len(parts):
        return None
    seg = parts[kind.scope_segment]
    if kind.scope_on_stem:
        seg = PurePosixPath(seg).stem
    return seg


def classify(rel: str, kinds: Sequence[ArtifactKind] = REGISTRY) -> Classification:
    """telemetry 루트 기준 상대경로(posix) → Classification (FS 비변경, 순수)."""
    rel = PurePosixPath(rel).as_posix()
    name = PurePosixPath(rel).name
    collision_n, canonical_name = _parse_collision(name)
    canonical_rel = PurePosixPath(rel).with_name(canonical_name).as_posix()
    date = _extract_date(canonical_name)

    kind = _match_kind(rel, kinds)
    if kind is None:
        return Classification(
            rel=rel, kind=None, retention_class=None, scope=None, date=date,
            collision_n=collision_n, canonical_rel=canonical_rel,
            verdict=ORPHAN, reason="어떤 registry kind glob 에도 미매칭 (생산자 소멸/미등록)",
        )

    scope = _extract_scope(canonical_rel, kind)

    if kind.id_validator is not None and (scope is None or not re.match(kind.id_validator, scope)):
        return Classification(
            rel=rel, kind=kind.kind, retention_class=kind.retention_class, scope=scope,
            date=date, collision_n=collision_n, canonical_rel=canonical_rel,
            verdict=ORPHAN,
            reason=f"scope={scope!r} 가 id_validator({kind.id_validator}) 위반",
        )

    if not producer_exists(kind):
        return Classification(
            rel=rel, kind=kind.kind, retention_class=kind.retention_class, scope=scope,
            date=date, collision_n=collision_n, canonical_rel=canonical_rel,
            verdict=LEGACY,
            reason=f"producer_module={kind.producer_module!r} 부재 (생산자 소멸)",
        )

    return Classification(
        rel=rel, kind=kind.kind, retention_class=kind.retention_class, scope=scope,
        date=date, collision_n=collision_n, canonical_rel=canonical_rel,
        verdict=CANDIDATE, reason="",
    )


def scan(root: Path, kinds: Sequence[ArtifactKind] = REGISTRY) -> list[Classification]:
    """telemetry 루트 트리 walk → Classification 목록 (메타 파일 skip)."""
    out: list[Classification] = []
    if not root.exists():
        return out
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        if p.name in _IGNORE_NAMES:
            continue
        rel = p.relative_to(root).as_posix()
        out.append(classify(rel, kinds))
    return out


# ============================================================
# GC planner (Task 5)
# ============================================================


def _date_lt(a: str | None, b: str | None) -> bool:
    """a < b (date string YYYY-MM-DD; None 은 가장 과거로 취급)."""
    return (a or "") < (b or "")


def plan_gc(
    classifications: Iterable[Classification],
    *,
    keep_days: int | None = None,
    today: str | None = None,
) -> GCPlan:
    """Classification 목록 → GCPlan. 순수(FS 비변경). 결정론(collision_n 기준).

    keep_days: EPHEMERAL(dated) 산출물을 today-keep_days 이전이면 prune (None=age-prune 안 함).
    today: age-prune 기준일 (YYYY-MM-DD). keep_days 지정 시 필요.
    """
    plan = GCPlan()

    # 1) canonical_rel 로 그룹화 (collision 묶음).
    groups: dict[str, list[Classification]] = {}
    for c in classifications:
        groups.setdefault(c.canonical_rel, []).append(c)

    # 2) canonical 단위 1차 판정 → ORPHAN/LEGACY 즉시 삭제, CANDIDATE 는 survivors 로.
    #    survivors[canonical_rel] = 대표 Classification (canonical 기준 메타).
    survivors: dict[str, Classification] = {}
    for canonical_rel, members in groups.items():
        rep = members[0]
        if rep.verdict == ORPHAN:
            for m in members:
                plan.delete.append(m.rel)
                plan.orphans.append(m.rel)
            continue
        if rep.verdict == LEGACY:
            for m in members:
                plan.delete.append(m.rel)
                plan.legacy.append(m.rel)
            continue
        survivors[canonical_rel] = rep

    # 3) SNAPSHOT supersession — (kind, scope) 그룹 내 최신 date 1건 유지.
    snap_groups: dict[tuple[str, str | None], list[str]] = {}
    for canonical_rel, rep in survivors.items():
        if rep.retention_class == RetentionClass.SNAPSHOT:
            snap_groups.setdefault((rep.kind, rep.scope), []).append(canonical_rel)

    superseded: set[str] = set()
    for _key, crels in snap_groups.items():
        if len(crels) <= 1:
            continue
        # 최신 date 1건 유지 (date 동률이면 canonical_rel 사전순 최대 = 결정론).
        latest = max(crels, key=lambda cr: (survivors[cr].date or "", cr))
        for cr in crels:
            if cr != latest:
                superseded.add(cr)

    # 4) EPHEMERAL age-prune (옵션).
    aged_out: set[str] = set()
    if keep_days is not None and today is not None:
        cutoff = (
            datetime.strptime(today, "%Y-%m-%d") - timedelta(days=keep_days)
        ).strftime("%Y-%m-%d")
        for canonical_rel, rep in survivors.items():
            if (
                rep.retention_class == RetentionClass.EPHEMERAL
                and rep.date is not None
                and _date_lt(rep.date, cutoff)
            ):
                aged_out.add(canonical_rel)

    # 5) survivor 별 collision-collapse + 삭제/유지 확정.
    for canonical_rel in survivors:
        members = groups[canonical_rel]
        drop_logical = canonical_rel in superseded or canonical_rel in aged_out

        if drop_logical:
            for m in members:
                plan.delete.append(m.rel)
                if canonical_rel in superseded:
                    plan.stale.append(m.rel)
            continue

        # collision-collapse: 최신(max collision_n) 1개만 canonical 로.
        winner = max(members, key=lambda m: m.collision_n)
        for m in members:
            if m.rel != winner.rel:
                plan.delete.append(m.rel)
        if winner.collision_n > 0:
            plan.normalize.append((winner.rel, canonical_rel))
        plan.keep.append(canonical_rel)

    # 결정론 정렬.
    plan.delete.sort()
    plan.normalize.sort()
    plan.keep.sort()
    plan.orphans.sort()
    plan.legacy.sort()
    plan.stale.sort()
    return plan
