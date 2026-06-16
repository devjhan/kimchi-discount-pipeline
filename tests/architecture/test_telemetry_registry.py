"""불변식 — Telemetry Artifact Registry 내부 일관성 + 생산자 존재성.

``infrastructure._common.telemetry_registry.REGISTRY`` 가 telemetry/ 산출물 종류의
선언적 SSoT 다. 본 fitness function 은:

1. kind 식별자 / glob 이 유일한지 (중복 선언 금지).
2. 선언된 ``producer_module`` 이 repo 에 실제 존재하는지 (생산자 소멸 = drift → red).
3. glob 이 알려진 telemetry subdir prefix 하에 있는지 (오타/오배치 차단).
4. id_validator 정규식이 컴파일되는지.

"디스크 파일 == 레지스트리 kind" 의 live no-orphan 단언은 일회성 정리(Task 8) 이후
GC 스캐너가 담당 — 본 모듈은 레지스트리 자체의 무결성을 고정한다.
"""
from __future__ import annotations

import re

import pytest

from infrastructure._common import telemetry_registry as reg
from infrastructure._common import utils as _utils

_KNOWN_PREFIXES = (
    "positions/",
    "nav-history/",
    "external_signals/",
    "segments/",
    "audit/",
    "policy_drafts/",
    "logs/",
)


@pytest.mark.arch
def test_registry_kind_names_unique() -> None:
    names = [k.kind for k in reg.REGISTRY]
    dupes = {n for n in names if names.count(n) > 1}
    assert not dupes, f"중복 kind 식별자: {sorted(dupes)}"


@pytest.mark.arch
def test_registry_globs_unique() -> None:
    globs = [k.glob for k in reg.REGISTRY]
    dupes = {g for g in globs if globs.count(g) > 1}
    assert not dupes, f"중복 glob: {sorted(dupes)}"


@pytest.mark.arch
@pytest.mark.parametrize("kind", reg.REGISTRY, ids=lambda k: k.kind)
def test_producer_module_exists(kind: reg.ArtifactKind) -> None:
    """선언된 생산자 모듈이 repo 에 존재 (None=외부 생산자는 skip)."""
    if kind.producer_module is None:
        pytest.skip("외부 생산자(skill/shell/manual) — 모듈 존재성 N/A")
    assert reg.producer_exists(kind), (
        f"kind={kind.kind} 의 producer_module={kind.producer_module!r} 파일 부재 "
        "— 생산자 소멸(legacy) 또는 dotted path 오타"
    )


@pytest.mark.arch
@pytest.mark.parametrize("kind", reg.REGISTRY, ids=lambda k: k.kind)
def test_glob_under_known_prefix(kind: reg.ArtifactKind) -> None:
    assert kind.glob.startswith(_KNOWN_PREFIXES), (
        f"kind={kind.kind} glob={kind.glob!r} 가 알려진 telemetry subdir prefix 밖"
    )


@pytest.mark.arch
@pytest.mark.parametrize("kind", reg.REGISTRY, ids=lambda k: k.kind)
def test_id_validator_compiles(kind: reg.ArtifactKind) -> None:
    if kind.id_validator is None:
        pytest.skip("id_validator 없음")
    re.compile(kind.id_validator)  # raises on invalid


@pytest.mark.arch
@pytest.mark.parametrize("kind", reg.REGISTRY, ids=lambda k: k.kind)
def test_retention_class_valid(kind: reg.ArtifactKind) -> None:
    assert isinstance(kind.retention_class, reg.RetentionClass)


@pytest.mark.arch
def test_scope_segment_consistency() -> None:
    """scope_on_stem / id_validator 는 scope_segment 가 지정된 kind 에서만 의미."""
    for k in reg.REGISTRY:
        if k.scope_on_stem:
            assert k.scope_segment is not None, f"{k.kind}: scope_on_stem 인데 scope_segment 없음"
        if k.id_validator is not None:
            assert k.scope_segment is not None, f"{k.kind}: id_validator 인데 scope_segment 없음"


@pytest.mark.arch
def test_live_telemetry_has_no_orphans() -> None:
    """실제 telemetry/ 트리에 미등록(ORPHAN)/생산자소멸(LEGACY) 산출물이 없어야 한다.

    신규 산출물 종류 추가 시 레지스트리 등록을 강제하는 드리프트 가드 — "체계적으로 저장되지
    않는 산출물" 재발 방지. telemetry/ 부재(CI 등) 시 skip.
    """
    from infrastructure._common import telemetry_gc as gc

    root = reg.telemetry_root()
    if not root.exists():
        pytest.skip("telemetry/ 부재")
    offenders = [
        (c.rel, c.verdict, c.reason)
        for c in gc.scan(root)
        if c.verdict in (gc.ORPHAN, gc.LEGACY)
    ]
    assert not offenders, (
        f"telemetry/ 에 미등록/legacy 산출물: {offenders} — "
        "registry(telemetry_registry.REGISTRY) 등록 또는 `make telemetry-gc-apply` 정리 필요"
    )


@pytest.mark.arch
def test_registry_kinds_documented_in_skill() -> None:
    """모든 REGISTRY.kind 가 context-telemetry 스킬 artifact-registry.md 에 등재됐는지 (문서-코드 동기화)."""
    doc = (
        _utils.REPO_ROOT
        / ".agents/skills/context-telemetry/common/artifact-registry.md"
    )
    assert doc.exists(), "context-telemetry/common/artifact-registry.md 부재"
    text = doc.read_text(encoding="utf-8")
    missing = [k.kind for k in reg.REGISTRY if k.kind not in text]
    assert not missing, f"스킬 문서에 누락된 kind: {missing} (artifact-registry.md 표 갱신 필요)"

