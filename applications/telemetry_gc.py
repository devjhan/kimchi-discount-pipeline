#!/usr/bin/env python3
"""telemetry retention GC — CLI 실행기.

``infrastructure._common.telemetry_registry`` (kind SSoT) + ``telemetry_gc`` (분류기/planner)
를 소비해 telemetry/ 트리를 스캔하고 retention 정책에 따른 정리 계획을 산출/실행한다.

정책 (ADR retention class):
  - PERMANENT (nav-history / external_signals / violations / breadth / subsidiaries / trade-log):
    distinct date 전부 보존 (+ .{N} 충돌본 정규화).
  - STATE (thesis.json/md / shadow state): living 단일 파일, prune 안 함 (충돌본 정규화만).
  - SNAPSHOT (account summary/derived / balance / drift / expiry / scheduler-state):
    (kind, scope)별 최신 1건만 유지 (나머지 stale → 삭제).
  - BINARY (segments/vectors.sqlite): 보존.
  - EPHEMERAL (logs / policy_drafts): --keep-logs-days N 지정 시 age-prune.
  - ORPHAN (어떤 kind 에도 미매칭 / id_validator 위반) · LEGACY (생산자 모듈 소멸) → 삭제.

usage:
    python -m applications.telemetry_gc                 # dry-run (기본, 변경 없음)
    python -m applications.telemetry_gc --apply         # 실제 삭제/정규화 수행
    python -m applications.telemetry_gc --keep-logs-days 30 --apply
    python -m applications.telemetry_gc --root /tmp/telemetry --apply   # 루트 override(테스트)

안전: 기본 dry-run. --apply 명시해야만 FS 변경. 삭제 대상은 SNAPSHOT 초과분 / 충돌본 /
ORPHAN / LEGACY 로 한정 — PERMANENT/STATE/BINARY 증거는 불변.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from infrastructure._common import telemetry_gc as gc
from infrastructure._common import utils as _utils
from infrastructure._common.telemetry_registry import telemetry_root


def build_plan(
    root: Path, *, keep_days: int | None = None, today: str | None = None
) -> gc.GCPlan:
    """root 스캔 → GCPlan (FS 비변경)."""
    classifications = gc.scan(root)
    return gc.plan_gc(classifications, keep_days=keep_days, today=today)


def _remove_empty_dirs(root: Path) -> list[str]:
    """root 하위 빈 디렉토리 bottom-up 제거 (root 자신은 제외). 제거된 rel 목록 반환.

    .gitkeep 를 가진 디렉토리는 비어있지 않으므로 보존된다.
    """
    removed: list[str] = []
    for d in sorted((p for p in root.rglob("*") if p.is_dir()), reverse=True):
        try:
            next(d.iterdir())
        except StopIteration:
            rel = d.relative_to(root).as_posix()
            d.rmdir()
            removed.append(rel)
    return removed


def execute_plan(root: Path, plan: gc.GCPlan) -> dict[str, int]:
    """plan 적용 (FS 변경). delete → normalize 순서 (canonical 자리 비운 뒤 rename)."""
    deleted = 0
    for rel in plan.delete:
        p = root / rel
        if p.exists():
            p.unlink()
            deleted += 1
    renamed = 0
    for src_rel, dst_rel in plan.normalize:
        src = root / src_rel
        dst = root / dst_rel
        if src.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            src.rename(dst)
            renamed += 1
    removed_dirs = _remove_empty_dirs(root)
    return {"deleted": deleted, "renamed": renamed, "removed_dirs": len(removed_dirs)}


def format_plan(plan: gc.GCPlan, root: Path, *, applied: bool) -> str:
    lines: list[str] = []
    header = "APPLIED" if applied else "DRY-RUN (변경 없음 — --apply 로 실행)"
    lines.append(f"=== telemetry retention GC :: {header} ===")
    lines.append(f"root: {root}")
    lines.append("")
    lines.append(f"keep      : {len(plan.keep)}")
    lines.append(f"normalize : {len(plan.normalize)}  (.{{N}} 충돌본 → canonical)")
    lines.append(f"delete    : {len(plan.delete)}  "
                 f"(orphan={len(plan.orphans)} legacy={len(plan.legacy)} stale={len(plan.stale)})")
    if plan.normalize:
        lines.append("")
        lines.append("-- normalize --")
        for src, dst in plan.normalize:
            lines.append(f"  {src}  →  {dst}")
    if plan.delete:
        lines.append("")
        lines.append("-- delete --")
        for rel in plan.delete:
            tag = (
                "orphan" if rel in plan.orphans
                else "legacy" if rel in plan.legacy
                else "stale" if rel in plan.stale
                else "collision"
            )
            lines.append(f"  [{tag}] {rel}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="telemetry retention GC")
    parser.add_argument(
        "--apply", action="store_true",
        help="실제 삭제/정규화 수행 (미지정 시 dry-run).",
    )
    parser.add_argument(
        "--keep-logs-days", type=int, default=None,
        help="EPHEMERAL(logs/policy_drafts) age-prune 일수 (미지정 시 age-prune 안 함).",
    )
    parser.add_argument(
        "--root", default=None,
        help="telemetry 루트 override (기본: $TELEMETRY_DIR → telemetry/).",
    )
    parser.add_argument(
        "--today", default=None,
        help="age-prune 기준일 YYYY-MM-DD (기본: KST 오늘).",
    )
    args = parser.parse_args(argv)

    root = Path(args.root) if args.root else telemetry_root()
    today = args.today or _utils.now_iso_kst()[:10]

    plan = build_plan(root, keep_days=args.keep_logs_days, today=today)

    if args.apply:
        stats = execute_plan(root, plan)
        print(format_plan(plan, root, applied=True))
        print("")
        print(f"[applied] deleted={stats['deleted']} renamed={stats['renamed']} "
              f"removed_dirs={stats['removed_dirs']}")
    else:
        print(format_plan(plan, root, applied=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
