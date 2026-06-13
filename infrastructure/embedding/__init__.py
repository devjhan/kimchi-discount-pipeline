"""infrastructure/embedding — 원격 임베딩 API (OpenAI-호환 /embeddings) 단일 게이트.

primitive 만 반환 — EmbeddingPort 계약 변환은 domains/_shared/adapters/embedding_remote.
"""
from __future__ import annotations

from infrastructure.embedding.client import (
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    EmbeddingUnavailable,
    embed_texts,
    has_embedding_key,
    resolve_base_url,
    resolve_model,
)

__all__ = [
    "DEFAULT_BASE_URL",
    "DEFAULT_MODEL",
    "EmbeddingUnavailable",
    "embed_texts",
    "has_embedding_key",
    "resolve_base_url",
    "resolve_model",
]
