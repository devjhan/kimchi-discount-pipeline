"""
불변식 — ADR-0014: governance/policy/ 의 디렉토리 트리가 통합 스키마의 scope 축을 미러한다.

profile 은 단일 ``policy-profile-v1`` 객체이고 유일한 분기축은 ``scope ∈ {global, segment,
ticker}`` 다. 따라서 저장 위치도 그 축을 그대로 반영한다:

    governance/policy/profiles/<scope>/<key>/v<N>.yaml   (scope == 부모 버킷)

본 fitness function 은 *오배치* 를 빌드 에러로 만든다 — scope=ticker 파일이 profiles/segment/
밑에 들어가면 즉시 red. 구조적 직관성을 코드로 고정 (문서 의존 X).
"""

from __future__ import annotations

import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import pytest  # noqa: E402
import yaml  # noqa: E402

import _helpers as h  # noqa: E402

_POLICY_ROOT = h.REPO_ROOT / "governance" / "policy"
_PROFILES_ROOT = _POLICY_ROOT / "profiles"
_SCOPES = ("global", "segment", "ticker")
_VERSION_RE = re.compile(r"^v\d+\.yaml$")

# ADR-0014 승인 top-level 엔트리 (디렉토리 + singleton 파일).
_ALLOWED_TOP_LEVEL = frozenset(
    {"profiles", "segments", "concepts", "strategies", "hard_guards.yaml", "methods_manifest.yaml"}
)


def _profile_version_files() -> list[pathlib.Path]:
    out: list[pathlib.Path] = []
    for scope in _SCOPES:
        d = _PROFILES_ROOT / scope
        if d.exists():
            out.extend(p for p in d.rglob("v*.yaml") if _VERSION_RE.match(p.name))
    return out


@pytest.mark.arch
def test_profiles_bucketed_by_scope_dirs() -> None:
    """profiles/ 하위는 정확히 scope 버킷(global/segment/ticker)만 갖는다."""
    assert _PROFILES_ROOT.is_dir(), "governance/policy/profiles 부재 (ADR-0014)"
    children = {c.name for c in _PROFILES_ROOT.iterdir() if c.is_dir()}
    unexpected = children - set(_SCOPES)
    assert not unexpected, f"profiles/ 에 예상 밖 버킷: {sorted(unexpected)} (허용: {_SCOPES})"


@pytest.mark.arch
@pytest.mark.parametrize("path", _profile_version_files(), ids=h.rel)
def test_profile_scope_field_matches_bucket(path: pathlib.Path) -> None:
    """profiles/<scope>/.../v<N>.yaml 의 ``scope:`` 필드 == 부모 버킷 (오배치 금지)."""
    bucket = path.relative_to(_PROFILES_ROOT).parts[0]
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    on_disk_scope = raw.get("scope")
    assert on_disk_scope == bucket, (
        f"{h.rel(path)}: scope={on_disk_scope!r} 인데 버킷은 {bucket!r} — "
        "scope 필드와 디렉토리가 불일치 (ADR-0014 path↔scope 불변식)"
    )


@pytest.mark.arch
def test_profiles_use_versioned_layout_only() -> None:
    """profiles/<scope>/ 밑의 정책 파일은 <key>/v<N>.yaml 형태만 (flat .yaml 금지)."""
    offenders: list[str] = []
    for scope in _SCOPES:
        d = _PROFILES_ROOT / scope
        if not d.is_dir():
            continue
        # scope 버킷 바로 아래에 .yaml 이 있으면 versioned-dir 규약 위반 (flat 잔존).
        for p in d.iterdir():
            if p.is_file() and p.suffix == ".yaml":
                offenders.append(h.rel(p))
        # <key>/ 아래 파일은 v<N>.yaml 만 허용.
        for key_dir in (c for c in d.iterdir() if c.is_dir()):
            for p in key_dir.iterdir():
                if p.is_file() and p.suffix == ".yaml" and not _VERSION_RE.match(p.name):
                    offenders.append(h.rel(p))
    assert not offenders, f"flat/비-versioned 정책 파일 발견 (ADR-0014 v<N>.yaml 규약 위반): {offenders}"


@pytest.mark.arch
def test_policy_root_top_level_is_clean() -> None:
    """governance/policy/ top-level 은 승인된 엔트리만 갖는다 (구 global/·segment_profiles/ 금지)."""
    present = {c.name for c in _POLICY_ROOT.iterdir() if not c.name.startswith(".")}
    unexpected = present - _ALLOWED_TOP_LEVEL
    assert not unexpected, (
        f"governance/policy/ 에 예상 밖 엔트리: {sorted(unexpected)} "
        f"(허용: {sorted(_ALLOWED_TOP_LEVEL)}; ADR-0014)"
    )
