"""RemoteEmbeddingAdapter — EmbeddingPort 구현 (주입형 transport, infra import 0).

``domains/_shared/adapters/disclosure_scan`` 과 동형: 외부 접촉은 *주입된 transport*
(raw HTTP 호출, ``infrastructure/embedding/client.embed_texts`` 를 BC ``_boundary`` 가
바인딩) 로만 한다. 본 모듈은 그 primitive 결과를 ``EmbeddingResult`` 계약으로 변환하고
graceful skip(키/런타임 부재 → status='skipped')을 책임진다 (G8/G11).
"""
from __future__ import annotations

from typing import Callable, Sequence

from domains._shared.ports.embedding import EmbeddingResult

# transport(texts) -> (vectors, model_id, dim). 실패 시 예외 raise (adapter 가 wrap).
Transport = Callable[[Sequence[str]], "tuple[list[list[float]], str, int]"]


class RemoteEmbeddingAdapter:
    """EmbeddingPort 구현. transport 주입 (테스트는 fake, 운영은 infra client 바인딩)."""

    def __init__(
        self,
        *,
        transport: Transport,
        model_id: str,
        available: bool = True,
        dry_run: bool = False,
    ) -> None:
        self._transport = transport
        self._model_id = model_id
        self._available = available
        self._dry_run = dry_run
        self._dim = 0

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def dim(self) -> int:
        return self._dim

    def embed(self, texts: Sequence[str]) -> EmbeddingResult:
        if not texts:
            return EmbeddingResult(status="ok", model_id=self._model_id, dim=self._dim)
        if not self._available:
            return EmbeddingResult(
                status="skipped",
                model_id=self._model_id,
                skip_reason="EMBEDDING_API_KEY 미설정 — semantic membership UNKNOWN",
            )
        if self._dry_run:
            return EmbeddingResult(
                status="skipped", model_id=self._model_id, skip_reason="dry_run"
            )
        try:
            vectors, model, dim = self._transport(list(texts))
        except Exception as exc:  # noqa: BLE001 — graceful (키 미노출)
            return EmbeddingResult(
                status="error",
                model_id=self._model_id,
                error=f"{type(exc).__name__}: {exc}",
            )
        self._dim = dim
        return EmbeddingResult(
            status="ok",
            model_id=model or self._model_id,
            dim=dim,
            vectors=tuple(tuple(float(x) for x in v) for v in vectors),
        )
