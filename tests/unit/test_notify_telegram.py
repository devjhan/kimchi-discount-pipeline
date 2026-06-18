"""tests/unit/test_notify_telegram.py — Telegram Bot API adapter (ADR-0017).

``TelegramAdapter`` 는 cloud routine MCP 없이 stdlib ``urllib`` 로 로컬 직접 발송한다.
urlopen 은 mock — 외부 네트워크 없이 호출 URL/payload/청킹만 검증.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from infrastructure.notify.telegram import CHUNK_SIZE, TelegramAdapter

pytestmark = pytest.mark.unit

ENV = {"TELEGRAM_BOT_TOKEN": "123:ABCsecrettoken", "TELEGRAM_CHAT_ID": "987654"}


def test_is_ready_missing_env() -> None:
    adapter = TelegramAdapter(env={"TELEGRAM_BOT_TOKEN": "x"})
    ready, missing = adapter.is_ready()
    assert ready is False
    assert "TELEGRAM_CHAT_ID" in missing


def test_is_ready_full_env() -> None:
    adapter = TelegramAdapter(env=dict(ENV))
    ready, missing = adapter.is_ready()
    assert ready is True
    assert missing is None


def test_render_single_chunk() -> None:
    adapter = TelegramAdapter(env=dict(ENV))
    payload = adapter.render("short brief")
    assert payload["chat_id"] == "987654"
    assert payload["_total"] == 1
    assert payload["chunks"] == ["short brief"]


def test_render_multi_chunk() -> None:
    adapter = TelegramAdapter(env=dict(ENV))
    big = "A" * (CHUNK_SIZE + 100)
    payload = adapter.render(big)
    assert payload["_total"] == 2
    assert len(payload["chunks"][0]) == CHUNK_SIZE
    assert len(payload["chunks"][1]) == 100


def test_send_dry_run_no_http() -> None:
    adapter = TelegramAdapter(env=dict(ENV))
    payload = adapter.render("brief")
    with patch("infrastructure.notify.telegram.urllib.request.urlopen") as m:
        result = adapter.send(payload, dry_run=True)
    assert result.status == "skipped"
    m.assert_not_called()


def test_send_posts_each_chunk() -> None:
    adapter = TelegramAdapter(env=dict(ENV))
    big = "A" * (CHUNK_SIZE + 50)  # → 2 청크
    payload = adapter.render(big)
    with patch("infrastructure.notify.telegram.urllib.request.urlopen") as m:
        result = adapter.send(payload, dry_run=False)
    assert result.status == "sent"
    assert m.call_count == 2
    req = m.call_args_list[0].args[0]
    assert "/bot123:ABCsecrettoken/sendMessage" in req.full_url
    assert b"chat_id=987654" in req.data


def test_send_error_redacts_token() -> None:
    adapter = TelegramAdapter(env=dict(ENV))
    payload = adapter.render("brief")
    with patch("infrastructure.notify.telegram.urllib.request.urlopen") as m:
        m.side_effect = RuntimeError(
            "POST failed: https://api.telegram.org/bot123:ABCsecrettoken/sendMessage"
        )
        result = adapter.send(payload, dry_run=False)
    assert result.status == "error"
    assert "123:ABCsecrettoken" not in (result.error or "")
    assert "<TELEGRAM_BOT_TOKEN_REDACTED>" in (result.error or "")
