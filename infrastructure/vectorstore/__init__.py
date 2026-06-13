"""infrastructure/vectorstore — 임베디드 벡터 + scalar 저장소 (sqlite, sqlite-vec 가속).

VectorIndexPort 를 구조적으로 충족 (domains import 0 — 불변식 A).
"""
from __future__ import annotations

from infrastructure.vectorstore.store import SqliteVectorStore

__all__ = ["SqliteVectorStore"]
