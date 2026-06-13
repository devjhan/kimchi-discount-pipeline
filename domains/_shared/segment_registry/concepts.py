"""ConceptDeclaration — semantic concept anchor 의 선언적 SSoT (9-a / 12-a).

concept = "의미론적으로 한 부분집합을 정의하는 anchor". 사용자가 ``governance/
concepts/<concept_id>/v<N>.yaml`` 에 **텍스트 설명**(임베딩 대상) 과/또는 **seed
tickers**, 그리고 기본 임계(threshold / top_k)를 선언한다. 본 선언으로부터 빌드 단계
(Task 9)가 anchor 벡터를 생성해 벡터 저장소에 적재하고, selector 의
``semantic_similarity`` leaf 가 cosine 으로 멤버십을 판정한다.

하우스 스타일: frozen dataclass + ``__post_init__`` 수동 검증 (Pydantic 아님).
on-disk YAML 헤더는 ``schema`` / ``version`` / ``description`` top-level (D-CFG-1).

본 모듈은 shape 만 검증한다. 임베딩 모델 / 벡터 차원 / 실제 유사도는 인프라
(EmbeddingPort / VectorIndexPort) 와 resolver 의 책임이다 (bc-independent kernel).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml

from domains._shared.segment_registry import _versioning
from domains._shared.segment_registry.attributes import NUMERIC_OPS
from domains._shared.segment_registry.errors import (
    ConceptNotFoundError,
    ConceptSchemaError,
)

CONCEPT_SCHEMA_VERSION = "segment-concept-v1"
"""bump => from_dict 가 마이그레이션 게이트로 reject. 호환 깨질 때만 올림."""


@dataclass(frozen=True)
class ConceptDeclaration:
    """단일 semantic concept anchor 선언. 임베딩 대상 텍스트 + 기본 임계 보유."""

    concept_id: str
    """short slug (예: "holdco_value_trap"). selector 의 ``concept`` 키와 매칭."""

    schema_version: str
    """== CONCEPT_SCHEMA_VERSION."""

    concept_version: int
    """concept 별 monotonic 정수 (1, 2, 3, ...)."""

    anchor_text: str
    """임베딩 대상 anchor 텍스트 (한국어 권장). 빈 문자열이면 seed_tickers 필수."""

    seed_tickers: tuple[str, ...] = ()
    """"KR:NNNNNN" seed 종목. anchor 벡터 보강 / centroid 산출에 사용 가능."""

    default_op: str = "ge"
    """semantic_similarity leaf 가 op 미지정 시 기본값 (numeric op)."""

    default_threshold: float | None = None
    """cosine 임계 기본값. selector leaf 가 threshold 미지정 시 사용."""

    default_top_k: int | None = None
    """top-k 멤버십 기본값. threshold 와 양립 — leaf 가 명시한 쪽 우선."""

    description: str = ""
    """D-CFG-1 헤더 미러 (사람용 1줄 의도)."""

    def __post_init__(self) -> None:
        if not self.concept_id or not self.concept_id.strip():
            raise ConceptSchemaError("concept_id 는 비어 있을 수 없음")
        if self.schema_version != CONCEPT_SCHEMA_VERSION:
            raise ConceptSchemaError(
                f"schema_version mismatch: {self.schema_version!r} "
                f"(expected {CONCEPT_SCHEMA_VERSION!r})"
            )
        if self.concept_version < 1:
            raise ConceptSchemaError("concept_version >= 1")
        if not self.anchor_text.strip() and not self.seed_tickers:
            raise ConceptSchemaError(
                f"concept {self.concept_id!r}: anchor_text 또는 seed_tickers 중 "
                "최소 하나는 있어야 함 (임베딩 대상 부재)"
            )
        if self.default_op not in NUMERIC_OPS:
            raise ConceptSchemaError(
                f"default_op 는 numeric op 여야 함: {self.default_op!r}"
            )
        if self.default_top_k is not None and self.default_top_k < 1:
            raise ConceptSchemaError("default_top_k >= 1")


def to_dict(c: ConceptDeclaration) -> dict[str, Any]:
    """ConceptDeclaration → on-disk dict (YAML dump 직전 형태)."""
    return {
        "schema": c.schema_version,
        "version": c.concept_version,
        "description": c.description,
        "concept_id": c.concept_id,
        "anchor_text": c.anchor_text,
        "seed_tickers": list(c.seed_tickers),
        "default_op": c.default_op,
        "default_threshold": c.default_threshold,
        "default_top_k": c.default_top_k,
    }


def from_dict(raw: Mapping[str, Any]) -> ConceptDeclaration:
    """on-disk dict → ConceptDeclaration. schema 게이트 + KeyError wrap."""
    sv = raw.get("schema")
    if sv != CONCEPT_SCHEMA_VERSION:
        raise ConceptSchemaError(
            f"unsupported schema: {sv!r} (expected {CONCEPT_SCHEMA_VERSION!r})"
        )
    try:
        return ConceptDeclaration(
            concept_id=raw["concept_id"],
            schema_version=sv,
            concept_version=int(raw["version"]),
            anchor_text=raw.get("anchor_text", "") or "",
            seed_tickers=tuple(raw.get("seed_tickers") or ()),
            default_op=raw.get("default_op", "ge"),
            default_threshold=(
                float(raw["default_threshold"])
                if raw.get("default_threshold") is not None
                else None
            ),
            default_top_k=(
                int(raw["default_top_k"])
                if raw.get("default_top_k") is not None
                else None
            ),
            description=raw.get("description", ""),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ConceptSchemaError(f"concept dict 파싱 실패: {exc}") from exc


@dataclass(frozen=True)
class ConceptRegistry:
    """concept 선언의 versioned read. root 는 caller 가 주입 (concepts_root()).

    레이아웃: ``<root>/<concept_id>/v<N>.yaml``. ProfileRegistry 와 동형 패턴.
    """

    root: Path

    def load_latest(self, concept_id: str) -> ConceptDeclaration | None:
        """최신 버전. 미등록 → None (Default No-Action). 손상 → ConceptSchemaError."""
        d = self.root / _versioning.id_dir(concept_id)
        versions = _versioning.sorted_versions(d)
        if not versions:
            return None
        return self.load_version(concept_id, versions[-1])

    def load_version(self, concept_id: str, version: int) -> ConceptDeclaration:
        """특정 버전 조회. 부재 → ConceptNotFoundError."""
        path = _versioning.version_path(self.root, concept_id, version)
        if not path.exists():
            raise ConceptNotFoundError(f"{concept_id} v{version} 부재: {path}")
        with path.open("r", encoding="utf-8") as f:
            return from_dict(yaml.safe_load(f) or {})

    def list_versions(self, concept_id: str) -> tuple[int, ...]:
        """등록 버전 오름차순 tuple. 미등록 → 빈 tuple."""
        d = self.root / _versioning.id_dir(concept_id)
        return tuple(_versioning.sorted_versions(d))

    def list_concepts(self) -> tuple[str, ...]:
        """root 하위, 버전 파일을 1개 이상 가진 모든 concept_id 정렬 tuple.

        concept_id 는 colon 없는 slug 이므로 디렉토리명 == concept_id (역치환 불요).
        """
        if not self.root.exists():
            return ()
        ids = [
            child.name
            for child in self.root.iterdir()
            if child.is_dir() and _versioning.sorted_versions(child)
        ]
        return tuple(sorted(ids))
