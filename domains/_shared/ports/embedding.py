"""EmbeddingPort — 텍스트 → 임베딩 벡터 생성 seam (순수 typing, infra import 0).

원격 임베딩 제공자(OpenAI-호환 ``/embeddings`` 등)의 형식 계약 (10-a). 구현(adapter)은
``infrastructure/embedding/`` 에 거주하며 ``EMBEDDING_API_KEY`` gate + graceful skip
(``infrastructure/llm`` 의 ``LlmResult`` 패턴과 동형). application/kernel 은 본 Protocol
에만 의존하고 composition root 가 adapter 를 주입한다 (D-CORE-4 / D-ARCH-4).

``EmbeddingResult`` 는 순수 데이터 계약 — infra import 0 이라 ports 에 거주 가능.
키 부재 / 런타임 부재 → ``status='skipped'`` (G11 default-no-action, 날조 금지 G8).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, Sequence, runtime_checkable


@dataclass(frozen=True)
class EmbeddingResult:
    """임베딩 호출 결과.

    status:
        'ok'      — vectors 채워짐 (len(vectors) == len(texts))
        'skipped' — 키/런타임 부재 → caller graceful degrade (semantic UNKNOWN)
        'error'   — 호출 자체 실패
    """

    status: str
    model_id: str = ""
    dim: int = 0
    vectors: tuple[tuple[float, ...], ...] = field(default_factory=tuple)
    skip_reason: str | None = None
    error: str | None = None


@runtime_checkable
class EmbeddingPort(Protocol):
    """텍스트 배치 → 임베딩 벡터. 부수효과는 원격 호출뿐 (저장 책임 없음)."""

    @property
    def model_id(self) -> str:
        """사용 모델 식별자 (provenance / 벡터 staleness 키)."""
        ...

    @property
    def dim(self) -> int:
        """임베딩 차원 (0 = 미확정 / skip)."""
        ...

    def embed(self, texts: Sequence[str]) -> EmbeddingResult:
        """``texts`` 를 임베딩. 키 부재 → status='skipped' (raise 금지)."""
        ...
