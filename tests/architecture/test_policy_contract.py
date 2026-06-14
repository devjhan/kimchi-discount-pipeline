"""
불변식 — ADR-0014: governance/policy/ 의 모든 정책 산출물이 단일 계약을 만족한다.

repo-wide fitness function — 디스크의 *모든* 정책 YAML 을 다음으로 검증:
1. serde 로드 가능 (schema/scope 합법) — 손상/미지원 = build red.
2. 참조 무결성 — segment.profile_ref → profiles/segment/<ref>/, selector concept →
   concepts/<id>/, strategy profile_ref → profiles/global/<name>/ 가 모두 실재.
3. manifest 적합성 — 모든 cutoff_rules 의 metric_path/op/type ∈ methods_manifest.yaml.
4. (레이아웃은 test_policy_layout.py 가 별도로 고정.)

dangling profile_ref / 환각 metric_path / 미지원 op 가 조용히 통과하던 구멍을 닫는다.
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import pytest  # noqa: E402
import yaml  # noqa: E402

import _helpers as h  # noqa: E402

from domains._shared.policy_profile import serde as _pp_serde  # noqa: E402
from domains._shared.segment_registry import _versioning  # noqa: E402
from domains._shared.segment_registry import serde as _seg_serde  # noqa: E402
from domains._shared.segment_registry.concepts import from_dict as _concept_from_dict  # noqa: E402
from domains._shared.segment_registry.selector import collect_concepts  # noqa: E402
from domains.policy.domain.cutoff_validate import validate_cutoff_rules  # noqa: E402
from domains.screener.main import _collect_profile_refs  # noqa: E402

_POLICY = h.REPO_ROOT / "governance" / "policy"
_MANIFEST = yaml.safe_load((_POLICY / "methods_manifest.yaml").read_text(encoding="utf-8"))


def _versioned_files(*subparts: str) -> list[pathlib.Path]:
    root = _POLICY.joinpath(*subparts)
    if not root.exists():
        return []
    return sorted(p for p in root.rglob("v*.yaml") if p.stem[1:].isdigit())


def _load(path: pathlib.Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


_PROFILE_FILES = (
    _versioned_files("profiles", "global")
    + _versioned_files("profiles", "segment")
    + _versioned_files("profiles", "ticker")
)
_SEGMENT_FILES = _versioned_files("segments")
_CONCEPT_FILES = _versioned_files("concepts")
_STRATEGY_FILES = _versioned_files("strategies")


# ----------------------------------------------------------------------
# 1. serde 로드 가능
# ----------------------------------------------------------------------
@pytest.mark.arch
@pytest.mark.parametrize("path", _PROFILE_FILES, ids=h.rel)
def test_profile_loads_via_serde(path: pathlib.Path) -> None:
    pp = _pp_serde.from_dict(_load(path))
    assert pp.scope in {"global", "segment", "ticker"}


@pytest.mark.arch
@pytest.mark.parametrize("path", _SEGMENT_FILES, ids=h.rel)
def test_segment_loads_via_serde(path: pathlib.Path) -> None:
    _seg_serde.segment_from_dict(_load(path))


@pytest.mark.arch
@pytest.mark.parametrize("path", _CONCEPT_FILES, ids=h.rel)
def test_concept_loads_via_serde(path: pathlib.Path) -> None:
    _concept_from_dict(_load(path))


@pytest.mark.arch
@pytest.mark.parametrize("path", _STRATEGY_FILES, ids=h.rel)
def test_strategy_has_required_shape(path: pathlib.Path) -> None:
    raw = _load(path)
    for key in ("name", "version", "rule"):
        assert key in raw, f"{h.rel(path)}: strategy 필수 키 {key!r} 부재"


# ----------------------------------------------------------------------
# 2. 참조 무결성
# ----------------------------------------------------------------------
def _has_versions(*subparts: str) -> bool:
    return bool(_versioning.sorted_versions(_POLICY.joinpath(*subparts)))


@pytest.mark.arch
@pytest.mark.parametrize("path", _SEGMENT_FILES, ids=h.rel)
def test_segment_profile_ref_resolves(path: pathlib.Path) -> None:
    seg = _seg_serde.segment_from_dict(_load(path))
    assert _has_versions("profiles", "segment", seg.profile_ref), (
        f"{h.rel(path)}: profile_ref {seg.profile_ref!r} → "
        f"governance/policy/profiles/segment/{seg.profile_ref}/ 부재 (dangling ref)"
    )


@pytest.mark.arch
@pytest.mark.parametrize("path", _SEGMENT_FILES, ids=h.rel)
def test_segment_concepts_resolve(path: pathlib.Path) -> None:
    raw = _load(path)
    for concept in collect_concepts(raw.get("selector") or {}):
        assert _has_versions("concepts", concept), (
            f"{h.rel(path)}: selector concept {concept!r} → "
            f"governance/policy/concepts/{concept}/ 부재 (dangling ref)"
        )


@pytest.mark.arch
@pytest.mark.parametrize("path", _STRATEGY_FILES, ids=h.rel)
def test_strategy_profile_refs_resolve(path: pathlib.Path) -> None:
    raw = _load(path)
    for ref in _collect_profile_refs(raw.get("rule") or {}):
        assert _has_versions("profiles", "global", ref), (
            f"{h.rel(path)}: strategy profile_ref {ref!r} → "
            f"governance/policy/profiles/global/{ref}/ 부재 (dangling ref)"
        )


# ----------------------------------------------------------------------
# 3. manifest 적합성 (cutoff metric_path/op/type ∈ methods_manifest.yaml)
# ----------------------------------------------------------------------
def _cutoff_specs() -> list[tuple[str, dict]]:
    """검증 대상 (label, cutoff_rules) — 비어있지 않은 profile cutoff + hard_guards 각 guard."""
    out: list[tuple[str, dict]] = []
    for path in _PROFILE_FILES:
        pp = _pp_serde.from_dict(_load(path))
        if pp.cutoff_rules:
            out.append((h.rel(path), dict(pp.cutoff_rules)))
    hg_path = _POLICY / "hard_guards.yaml"
    if hg_path.exists():
        for i, guard in enumerate(_load(hg_path).get("guards") or []):
            out.append((f"hard_guards.yaml::guards[{i}]", guard))
    return out


@pytest.mark.arch
@pytest.mark.parametrize("label,cutoff", _cutoff_specs(), ids=lambda v: v if isinstance(v, str) else "")
def test_cutoff_conforms_to_manifest(label: str, cutoff: dict) -> None:
    # validate_cutoff_rules 가 위반 시 CutoffContractError raise → test red.
    validate_cutoff_rules(cutoff, _MANIFEST)
