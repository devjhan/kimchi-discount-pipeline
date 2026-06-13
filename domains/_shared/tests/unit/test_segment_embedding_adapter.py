"""segment_registry — RemoteEmbeddingAdapter (EmbeddingPort) 단위 테스트 (Task 3)."""
from __future__ import annotations

import pytest

from domains._shared.adapters.embedding_remote import RemoteEmbeddingAdapter
from domains._shared.ports.embedding import EmbeddingPort, EmbeddingResult


def _ok_transport(texts):
    return ([[0.1, 0.2, 0.3] for _ in texts], "fake-model", 3)


@pytest.mark.unit
def test_adapter_is_embedding_port() -> None:
    a = RemoteEmbeddingAdapter(transport=_ok_transport, model_id="fake-model")
    assert isinstance(a, EmbeddingPort)


@pytest.mark.unit
def test_embed_ok() -> None:
    a = RemoteEmbeddingAdapter(transport=_ok_transport, model_id="fake-model")
    res = a.embed(["삼성", "현대"])
    assert isinstance(res, EmbeddingResult)
    assert res.status == "ok"
    assert res.dim == 3
    assert len(res.vectors) == 2
    assert a.dim == 3


@pytest.mark.unit
def test_embed_empty_is_ok_no_call() -> None:
    called = {"n": 0}

    def t(texts):
        called["n"] += 1
        return ([], "m", 0)

    a = RemoteEmbeddingAdapter(transport=t, model_id="m")
    res = a.embed([])
    assert res.status == "ok"
    assert called["n"] == 0  # 빈 입력 → transport 미호출


@pytest.mark.unit
def test_embed_unavailable_skips() -> None:
    a = RemoteEmbeddingAdapter(transport=_ok_transport, model_id="m", available=False)
    res = a.embed(["x"])
    assert res.status == "skipped"
    assert "EMBEDDING_API_KEY" in (res.skip_reason or "")


@pytest.mark.unit
def test_embed_dry_run_skips() -> None:
    a = RemoteEmbeddingAdapter(transport=_ok_transport, model_id="m", dry_run=True)
    res = a.embed(["x"])
    assert res.status == "skipped"
    assert res.skip_reason == "dry_run"


@pytest.mark.unit
def test_embed_transport_error_is_error_status() -> None:
    def boom(texts):
        raise RuntimeError("network down")

    a = RemoteEmbeddingAdapter(transport=boom, model_id="m")
    res = a.embed(["x"])
    assert res.status == "error"
    assert "network down" in (res.error or "")
