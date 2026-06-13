"""SegmentRegistry / NamedProfileRegistry — versioned read (root 주입, G20).

ProfileRegistry 와 동형 패턴: ``<root>/<id>/v<N>.yaml``, 신규 버전은 새 파일. root 는
caller(consumer ``_boundary.segments_root()`` / ``named_profiles_root()``)가 주입.

계층(parent) 순환 검출은 단일 segment shape 검증(``__post_init__``)으로 불가하므로
``detect_cycle`` / ``ancestor_chain`` 헬퍼로 다수 segment 를 함께 본다.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from domains._shared.segment_registry import _versioning, serde
from domains._shared.segment_registry.errors import (
    SegmentCycleError,
    SegmentNotFoundError,
)
from domains._shared.segment_registry.schema import (
    PolicyContribution,
    SegmentDefinition,
)


@dataclass(frozen=True)
class SegmentRegistry:
    """segment 선언의 versioned read. root = ``governance/policy/segments`` (주입)."""

    root: Path

    def load_latest(self, segment_id: str) -> SegmentDefinition | None:
        d = self.root / _versioning.id_dir(segment_id)
        versions = _versioning.sorted_versions(d)
        if not versions:
            return None
        return self.load_version(segment_id, versions[-1])

    def load_version(self, segment_id: str, version: int) -> SegmentDefinition:
        path = _versioning.version_path(self.root, segment_id, version)
        if not path.exists():
            raise SegmentNotFoundError(f"{segment_id} v{version} 부재: {path}")
        with path.open("r", encoding="utf-8") as f:
            return serde.segment_from_dict(yaml.safe_load(f) or {})

    def list_versions(self, segment_id: str) -> tuple[int, ...]:
        d = self.root / _versioning.id_dir(segment_id)
        return tuple(_versioning.sorted_versions(d))

    def list_segments(self) -> tuple[str, ...]:
        if not self.root.exists():
            return ()
        ids = [
            child.name
            for child in self.root.iterdir()
            if child.is_dir() and _versioning.sorted_versions(child)
        ]
        return tuple(sorted(ids))

    def load_all_latest(self) -> dict[str, SegmentDefinition]:
        """등록된 모든 segment 의 최신 버전 dict. cycle/parent 검증 입력용."""
        out: dict[str, SegmentDefinition] = {}
        for sid in self.list_segments():
            seg = self.load_latest(sid)
            if seg is not None:
                out[sid] = seg
        return out


@dataclass(frozen=True)
class NamedProfileRegistry:
    """segment 가 profile_ref 로 참조하는 named PolicyContribution 의 versioned read."""

    root: Path

    def load_latest(self, name: str) -> PolicyContribution | None:
        d = self.root / _versioning.id_dir(name)
        versions = _versioning.sorted_versions(d)
        if not versions:
            return None
        return self.load_version(name, versions[-1])

    def load_version(self, name: str, version: int) -> PolicyContribution:
        path = _versioning.version_path(self.root, name, version)
        if not path.exists():
            raise SegmentNotFoundError(f"named profile {name} v{version} 부재: {path}")
        with path.open("r", encoding="utf-8") as f:
            return serde.named_profile_from_dict(yaml.safe_load(f) or {})

    def list_versions(self, name: str) -> tuple[int, ...]:
        d = self.root / _versioning.id_dir(name)
        return tuple(_versioning.sorted_versions(d))


def ancestor_chain(
    segment_id: str, segments: dict[str, SegmentDefinition]
) -> list[str]:
    """``segment_id`` 의 root→...→self 조상 체인 (정렬: 가장 일반 → 구체).

    parent 가 segments 에 없으면 거기서 중단 (외부 미등록 parent 무시). 순환 →
    ``SegmentCycleError``.
    """
    chain: list[str] = []
    seen: set[str] = set()
    cur: str | None = segment_id
    while cur is not None and cur in segments:
        if cur in seen:
            raise SegmentCycleError(
                f"segment 계층 순환 검출: {cur!r} (체인: {chain})"
            )
        seen.add(cur)
        chain.append(cur)
        cur = segments[cur].parent
    chain.reverse()  # root → self
    return chain


def detect_cycle(segments: dict[str, SegmentDefinition]) -> None:
    """모든 segment 의 parent 체인에 순환이 있으면 ``SegmentCycleError``."""
    for sid in segments:
        ancestor_chain(sid, segments)  # raise on cycle
