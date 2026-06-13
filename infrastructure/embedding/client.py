"""infrastructure/embedding — 원격 임베딩 API client (OpenAI-호환 /embeddings, 10-a).

``infrastructure/llm`` 의 vendor-adapter 패턴과 동형이나 *chat* 이 아니라 *embeddings*
엔드포인트를 호출한다. 본 모듈은 **primitive 만 반환** (list[list[float]] + model + dim)
하고 ``domains`` 를 import 하지 않는다 (불변식 A — infra↛domains). EmbeddingPort 계약
(EmbeddingResult)으로의 변환은 ``domains/_shared/adapters/embedding_remote`` 가 담당.

키: ``EMBEDDING_API_KEY`` (필수), ``EMBEDDING_BASE_URL`` (기본 OpenAI), ``EMBEDDING_MODEL``.
``requests`` (기존 의존성) 사용 — ``openai`` SDK 불요. 키/요청 본문은 로그에 노출 금지(G21).
"""
from __future__ import annotations

from typing import Any, Callable, Sequence

import requests

DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "text-embedding-3-small"


class EmbeddingUnavailable(RuntimeError):
    """임베딩 호출 불가 (키 부재 / 네트워크 / API 오류). caller 가 graceful degrade."""


def has_embedding_key(env: dict[str, str]) -> bool:
    """``.env`` 의 EMBEDDING_API_KEY 존재 검사 (값 자체는 노출 금지)."""
    return bool(env.get("EMBEDDING_API_KEY"))


def resolve_model(env: dict[str, str]) -> str:
    """모델 선택: EMBEDDING_MODEL env → DEFAULT_MODEL."""
    return env.get("EMBEDDING_MODEL") or DEFAULT_MODEL


def resolve_base_url(env: dict[str, str]) -> str:
    return (env.get("EMBEDDING_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")


def embed_texts(
    texts: Sequence[str],
    *,
    api_key: str,
    base_url: str | None = None,
    model: str | None = None,
    timeout: float = 30.0,
    post: Callable[..., Any] | None = None,
) -> tuple[list[list[float]], str, int]:
    """``texts`` → (vectors, model, dim). 실패 시 ``EmbeddingUnavailable``.

    ``post`` 는 테스트 주입용 transport (기본 ``requests.post``). 반환 객체는
    ``raise_for_status()`` (선택) + ``json()`` 를 제공해야 한다 (OpenAI 응답 형식).
    """
    if not api_key:
        raise EmbeddingUnavailable("EMBEDDING_API_KEY 미설정")
    if not texts:
        return [], (model or DEFAULT_MODEL), 0
    url = f"{(base_url or DEFAULT_BASE_URL).rstrip('/')}/embeddings"
    use_model = model or DEFAULT_MODEL
    _post = post or requests.post
    try:
        resp = _post(
            url,
            json={"model": use_model, "input": list(texts)},
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout,
        )
        raise_for_status = getattr(resp, "raise_for_status", None)
        if callable(raise_for_status):
            raise_for_status()
        payload = resp.json()
        items = payload["data"]
        vectors = [[float(x) for x in item["embedding"]] for item in items]
        dim = len(vectors[0]) if vectors else 0
        if len(vectors) != len(texts):
            raise EmbeddingUnavailable(
                f"응답 벡터 수({len(vectors)}) != 입력 수({len(texts)})"
            )
        return vectors, use_model, dim
    except EmbeddingUnavailable:
        raise
    except Exception as exc:  # noqa: BLE001 — 모든 API 예외 graceful wrap (키 미노출)
        raise EmbeddingUnavailable(f"임베딩 호출 실패: {type(exc).__name__}: {exc}") from exc
