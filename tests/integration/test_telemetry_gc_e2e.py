"""tests/integration/test_telemetry_gc_e2e.py — GC 실행기 end-to-end (tmp 트리).

build_plan → execute_plan 이 retention 정책대로 삭제/정규화/빈디렉토리 제거를 수행하는지
실제 tmp FS 에서 검증. registry/classifier 의 생산자 존재성은 실제 repo 모듈을 본다.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from applications import telemetry_gc as cli

pytestmark = pytest.mark.integration


def _w(root: Path, rel: str, body: str = "{}") -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")
    return p


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    root = tmp_path / "telemetry"
    # SNAPSHOT account (collision)
    _w(root, "positions/_account/summary-2026-06-05.json", '{"v":"base"}')
    _w(root, "positions/_account/summary-2026-06-05.1.json", '{"v":"newer"}')
    _w(root, "positions/_account/derived-2026-06-05.json")
    # ORPHAN: bare ticker (id_validator 위반)
    _w(root, "positions/088350/balance-2026-06-05.json")
    # STATE: thesis.json (보존)
    _w(root, "positions/KR_003550/thesis.json", '{"status":"open"}')
    # SNAPSHOT per-ticker supersession
    _w(root, "positions/KR_003550/balance-2026-06-05.json")
    _w(root, "positions/KR_003550/balance-2026-06-10.json")
    # PERMANENT subsidiaries: distinct date 보존 + 06-15 충돌 정규화
    _w(root, "audit/subsidiaries/subsidiaries-audit-2026-06-07.json")
    _w(root, "audit/subsidiaries/subsidiaries-audit-2026-06-15.json", '{"v":"base"}')
    _w(root, "audit/subsidiaries/subsidiaries-audit-2026-06-15.1.json", '{"v":"newer"}')
    # PERMANENT 증거 (보존)
    _w(root, "audit/violations/universe/2026-06-16.jsonl")
    _w(root, "nav-history/KR_003550.jsonl")
    _w(root, "segments/vectors.sqlite", "binary")
    # ORPHAN: 생산자 소멸 hook log + 빈 디렉토리
    _w(root, "logs/_hook_audit.log", "log")
    (root / "logs" / "hooks").mkdir(parents=True, exist_ok=True)
    # .gitkeep 보존 대상
    _w(root, "audit/.gitkeep", "")
    return root


def test_dry_run_changes_nothing(tree: Path):
    before = sorted(p.relative_to(tree).as_posix() for p in tree.rglob("*") if p.is_file())
    plan = cli.build_plan(tree)
    # dry-run: execute 안 함
    after = sorted(p.relative_to(tree).as_posix() for p in tree.rglob("*") if p.is_file())
    assert before == after
    # plan 내용 sanity
    assert "logs/_hook_audit.log" in plan.orphans
    assert "positions/088350/balance-2026-06-05.json" in plan.orphans


def test_apply_executes_retention(tree: Path):
    plan = cli.build_plan(tree)
    cli.execute_plan(tree, plan)

    def exists(rel: str) -> bool:
        return (tree / rel).exists()

    # SNAPSHOT collision: .1 winner → canonical, base/.1 정리
    assert exists("positions/_account/summary-2026-06-05.json")
    assert not exists("positions/_account/summary-2026-06-05.1.json")
    assert (tree / "positions/_account/summary-2026-06-05.json").read_text() == '{"v":"newer"}'
    assert exists("positions/_account/derived-2026-06-05.json")

    # ORPHAN bare ticker → 파일 + 빈 디렉토리 제거
    assert not exists("positions/088350/balance-2026-06-05.json")
    assert not (tree / "positions/088350").exists()

    # STATE thesis.json 보존
    assert exists("positions/KR_003550/thesis.json")

    # SNAPSHOT per-ticker supersession: 최신만
    assert exists("positions/KR_003550/balance-2026-06-10.json")
    assert not exists("positions/KR_003550/balance-2026-06-05.json")

    # PERMANENT subsidiaries: 두 날짜 보존, 06-15 충돌 정규화
    assert exists("audit/subsidiaries/subsidiaries-audit-2026-06-07.json")
    assert exists("audit/subsidiaries/subsidiaries-audit-2026-06-15.json")
    assert not exists("audit/subsidiaries/subsidiaries-audit-2026-06-15.1.json")
    assert (tree / "audit/subsidiaries/subsidiaries-audit-2026-06-15.json").read_text() == '{"v":"newer"}'

    # PERMANENT 증거 보존
    assert exists("audit/violations/universe/2026-06-16.jsonl")
    assert exists("nav-history/KR_003550.jsonl")
    assert exists("segments/vectors.sqlite")

    # ORPHAN hook log + 빈 hooks 디렉토리 제거
    assert not exists("logs/_hook_audit.log")
    assert not (tree / "logs/hooks").exists()

    # .gitkeep 보존
    assert exists("audit/.gitkeep")


def test_apply_idempotent(tree: Path):
    """두 번째 실행은 변경 없음 (정리된 트리는 안정점)."""
    cli.execute_plan(tree, cli.build_plan(tree))
    plan2 = cli.build_plan(tree)
    assert plan2.delete == []
    assert plan2.normalize == []
