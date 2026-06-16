"""tests/unit/test_telemetry_gc.py — telemetry retention GC 분류기 + planner 단위 검증.

분류기(classify) / planner(plan_gc) 는 순수 로직 — FS 비변경. 실제 unlink/rename 실행기는
applications.telemetry_gc (integration 테스트 별도).
"""
from __future__ import annotations

import pytest

from infrastructure._common import telemetry_gc as gc
from infrastructure._common.telemetry_registry import (
    ArtifactKind,
    RetentionClass,
)

pytestmark = pytest.mark.unit


# ============================================================
# 분류기 (classify)
# ============================================================


def test_classify_account_summary_candidate():
    c = gc.classify("positions/_account/summary-2026-06-05.json")
    assert c.kind == "positions_account_summary"
    assert c.retention_class == RetentionClass.SNAPSHOT
    assert c.scope is None
    assert c.date == "2026-06-05"
    assert c.collision_n == 0
    assert c.canonical_rel == "positions/_account/summary-2026-06-05.json"
    assert c.verdict == gc.CANDIDATE


def test_classify_collision_suffix_parsed():
    c = gc.classify("positions/_account/summary-2026-06-05.1.json")
    assert c.collision_n == 1
    assert c.canonical_rel == "positions/_account/summary-2026-06-05.json"
    assert c.verdict == gc.CANDIDATE


def test_classify_subsidiaries_double_collision():
    c = gc.classify("audit/subsidiaries/subsidiaries-audit-2026-06-15.2.json")
    assert c.kind == "audit_subsidiaries"
    assert c.retention_class == RetentionClass.PERMANENT
    assert c.collision_n == 2
    assert c.canonical_rel == "audit/subsidiaries/subsidiaries-audit-2026-06-15.json"


def test_classify_legacy_ticker_format_is_orphan():
    """bare 6-digit ticker dir(088350)은 id_validator(^KR_\\d+$) 위반 → ORPHAN."""
    c = gc.classify("positions/088350/balance-2026-06-05.json")
    assert c.kind == "positions_ticker_balance"
    assert c.scope == "088350"
    assert c.verdict == gc.ORPHAN


def test_classify_valid_ticker_candidate():
    c = gc.classify("positions/KR_003550/balance-2026-06-05.json")
    assert c.scope == "KR_003550"
    assert c.verdict == gc.CANDIDATE


def test_classify_nav_history_scope_from_stem():
    c = gc.classify("nav-history/KR_003550.jsonl")
    assert c.kind == "nav_history"
    assert c.retention_class == RetentionClass.PERMANENT
    assert c.scope == "KR_003550"
    assert c.verdict == gc.CANDIDATE


def test_classify_violations_scope_is_bc():
    c = gc.classify("audit/violations/universe/2026-06-16.jsonl")
    assert c.kind == "audit_violations"
    assert c.scope == "universe"
    assert c.date == "2026-06-16"
    assert c.verdict == gc.CANDIDATE


def test_classify_hook_log_is_orphan():
    """ADR-0010 으로 파기된 hook 의 산출물 — 어떤 kind 에도 미매칭 → ORPHAN."""
    c = gc.classify("logs/_hook_audit.log")
    assert c.kind is None
    assert c.verdict == gc.ORPHAN


def test_classify_vectors_binary_kept():
    c = gc.classify("segments/vectors.sqlite")
    assert c.kind == "segments_vector_store"
    assert c.retention_class == RetentionClass.BINARY_EVIDENCE
    assert c.verdict == gc.CANDIDATE


def test_classify_unknown_path_orphan():
    c = gc.classify("audit/some-unregistered-thing-2026-06-16.json")
    assert c.kind is None
    assert c.verdict == gc.ORPHAN


def test_classify_legacy_producer_missing():
    """producer_module 이 repo 에 부재한 kind → LEGACY (드리프트 가드)."""
    fake = ArtifactKind(
        kind="fake_dead",
        glob="audit/dead/*.json",
        retention_class=RetentionClass.SNAPSHOT,
        producer_module="domains.nonexistent.ghost_module",
        producer="(없음)",
        dated=True,
    )
    c = gc.classify("audit/dead/x-2026-06-16.json", kinds=(fake,))
    assert c.verdict == gc.LEGACY


# ============================================================
# planner (plan_gc)
# ============================================================


def _classify_all(rels):
    return [gc.classify(r) for r in rels]


def test_plan_collision_collapse_keeps_latest_normalizes():
    """충돌본: 최신 collision_n 만 canonical 로 정규화, 나머지 삭제."""
    rels = [
        "audit/subsidiaries/subsidiaries-audit-2026-06-15.json",   # base (0)
        "audit/subsidiaries/subsidiaries-audit-2026-06-15.1.json",  # 1
        "audit/subsidiaries/subsidiaries-audit-2026-06-15.2.json",  # 2 (winner)
    ]
    plan = gc.plan_gc(_classify_all(rels))
    canonical = "audit/subsidiaries/subsidiaries-audit-2026-06-15.json"
    assert canonical in plan.keep
    assert (
        "audit/subsidiaries/subsidiaries-audit-2026-06-15.2.json",
        canonical,
    ) in plan.normalize
    assert "audit/subsidiaries/subsidiaries-audit-2026-06-15.json" in plan.delete  # base
    assert "audit/subsidiaries/subsidiaries-audit-2026-06-15.1.json" in plan.delete


def test_plan_permanent_keeps_all_distinct_dates():
    """PERMANENT(subsidiaries)은 distinct date 전부 보존 (supersession 없음)."""
    rels = [
        "audit/subsidiaries/subsidiaries-audit-2026-06-07.json",
        "audit/subsidiaries/subsidiaries-audit-2026-06-15.json",
    ]
    plan = gc.plan_gc(_classify_all(rels))
    assert set(plan.keep) == set(rels)
    assert plan.delete == []
    assert plan.stale == []


def test_plan_snapshot_supersession_keeps_latest_date():
    """SNAPSHOT(account summary)은 (kind,scope)별 최신 date 1건만 유지."""
    rels = [
        "positions/_account/summary-2026-06-05.json",
        "positions/_account/summary-2026-06-10.json",
    ]
    plan = gc.plan_gc(_classify_all(rels))
    assert plan.keep == ["positions/_account/summary-2026-06-10.json"]
    assert "positions/_account/summary-2026-06-05.json" in plan.delete
    assert "positions/_account/summary-2026-06-05.json" in plan.stale


def test_plan_snapshot_per_ticker_scope_independent():
    """SNAPSHOT supersession 은 scope(ticker)별로 독립."""
    rels = [
        "positions/KR_003550/balance-2026-06-05.json",
        "positions/KR_003550/balance-2026-06-10.json",
        "positions/KR_000270/balance-2026-06-05.json",
    ]
    plan = gc.plan_gc(_classify_all(rels))
    assert "positions/KR_003550/balance-2026-06-10.json" in plan.keep
    assert "positions/KR_000270/balance-2026-06-05.json" in plan.keep
    assert "positions/KR_003550/balance-2026-06-05.json" in plan.delete


def test_plan_orphan_and_legacy_deleted_whole_group():
    rels = [
        "positions/088350/balance-2026-06-05.json",    # orphan (id fail)
        "positions/088350/balance-2026-06-05.1.json",  # orphan collision
        "logs/_hook_audit.log",                         # orphan (no kind)
    ]
    plan = gc.plan_gc(_classify_all(rels))
    assert "positions/088350/balance-2026-06-05.json" in plan.orphans
    assert "positions/088350/balance-2026-06-05.1.json" in plan.orphans
    assert "logs/_hook_audit.log" in plan.orphans
    assert set(plan.orphans).issubset(set(plan.delete))
    assert plan.normalize == []
    assert plan.keep == []


def test_plan_state_and_binary_never_superseded():
    """STATE(thesis.json)/BINARY(vectors.sqlite)는 supersession 안 함 (충돌 정규화만)."""
    rels = [
        "positions/KR_003550/thesis.json",
        "segments/vectors.sqlite",
    ]
    plan = gc.plan_gc(_classify_all(rels))
    assert set(plan.keep) == set(rels)
    assert plan.delete == []


def test_plan_ephemeral_age_prune():
    """keep_days 지정 시 EPHEMERAL(dated) 오래된 것 prune; 최근 것 유지."""
    rels = [
        "logs/cron/run-2026-01-01.log",   # old
        "logs/cron/run-2026-06-15.log",   # recent
    ]
    plan = gc.plan_gc(_classify_all(rels), keep_days=30, today="2026-06-16")
    assert "logs/cron/run-2026-06-15.log" in plan.keep
    assert "logs/cron/run-2026-01-01.log" in plan.delete


def test_plan_ephemeral_no_prune_by_default():
    rels = ["logs/cron/run-2026-01-01.log"]
    plan = gc.plan_gc(_classify_all(rels))  # keep_days=None
    assert plan.keep == ["logs/cron/run-2026-01-01.log"]
    assert plan.delete == []


# ============================================================
# .gitignore 충돌본(.{N}) 패턴 검증 (git check-ignore 불가 환경 → fnmatch proxy)
# ============================================================

import fnmatch  # noqa: E402

# .gitignore 의 telemetry/**/*.[0-9]*.{ext} 패턴의 basename 부분.
_COLLISION_GLOBS = (
    "*.[0-9].json", "*.[0-9][0-9].json",
    "*.[0-9].jsonl", "*.[0-9][0-9].jsonl",
    "*.[0-9].md", "*.[0-9][0-9].md",
    "*.[0-9].csv", "*.[0-9][0-9].csv",
)


def _matches_collision(name: str) -> bool:
    return any(fnmatch.fnmatch(name, g) for g in _COLLISION_GLOBS)


def test_gitignore_pattern_matches_collision_dups():
    assert _matches_collision("summary-2026-06-05.1.json")
    assert _matches_collision("subsidiaries-audit-2026-06-15.2.json")
    assert _matches_collision("2026-06-16.1.jsonl")
    assert _matches_collision("drift-2026-06-05.1.md")
    assert _matches_collision("trade-log-tier_3_random.10.csv")  # 두 자리


def test_gitignore_pattern_skips_canonical_and_dated():
    """날짜본/canonical/증거 파일은 충돌본 패턴에 매칭되지 않아 계속 추적된다."""
    assert not _matches_collision("summary-2026-06-05.json")
    assert not _matches_collision("subsidiaries-audit-2026-06-15.json")
    assert not _matches_collision("2026-06-16.jsonl")          # violations/nav-history 날짜본
    assert not _matches_collision("KR_003550.jsonl")           # nav-history
    assert not _matches_collision("vectors.sqlite")            # binary 증거
    assert not _matches_collision("drift-2026-06-05.md")

