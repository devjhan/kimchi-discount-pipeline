"""infrastructure/embedding.client — embed_texts 단위 테스트 (Task 3, no network)."""
from __future__ import annotations

import pytest

from infrastructure.embedding.client import (
    EmbeddingUnavailable,
    embed_texts,
    has_embedding_key,
    resolve_model,
)


class _FakeResp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def _fake_post(payload):
    def post(url, json, headers, timeout):  # noqa: A002 — mirror requests.post kw
        return _FakeResp(payload)

    return post


@pytest.mark.unit
def test_has_key() -> None:
    assert has_embedding_key({"EMBEDDING_API_KEY": "x"})
    assert not has_embedding_key({})


@pytest.mark.unit
def test_resolve_model_default() -> None:
    assert resolve_model({}) == "text-embedding-3-small"
    assert resolve_model({"EMBEDDING_MODEL": "m2"}) == "m2"


@pytest.mark.unit
def test_embed_ok() -> None:
    payload = {"data": [{"embedding": [0.1, 0.2]}, {"embedding": [0.3, 0.4]}]}
    vectors, model, dim = embed_texts(
        ["a", "b"], api_key="k", model="m", post=_fake_post(payload)
    )
    assert dim == 2
    assert len(vectors) == 2
    assert model == "m"


@pytest.mark.unit
def test_embed_missing_key_raises() -> None:
    with pytest.raises(EmbeddingUnavailable):
        embed_texts(["a"], api_key="")


@pytest.mark.unit
def test_embed_empty_input_short_circuits() -> None:
    vectors, model, dim = embed_texts([], api_key="k")
    assert vectors == [] and dim == 0


@pytest.mark.unit
def test_embed_count_mismatch_raises() -> None:
    payload = {"data": [{"embedding": [0.1]}]}  # 1 vector for 2 inputs
    with pytest.raises(EmbeddingUnavailable):
        embed_texts(["a", "b"], api_key="k", post=_fake_post(payload))


@pytest.mark.unit
def test_embed_http_error_wrapped() -> None:
    def bad_post(url, json, headers, timeout):  # noqa: A002
        raise ConnectionError("boom")

    with pytest.raises(EmbeddingUnavailable):
        embed_texts(["a"], api_key="k", post=bad_post)
