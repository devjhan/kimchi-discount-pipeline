"""
infrastructure/notify/telegram.py — Telegram Bot API adapter.

브리프를 Telegram Bot API 로 **로컬에서 직접 발송**한다 (cloud routine MCP 불필요).
ADR-0017 — local direct notify.

stdlib ``urllib`` 로 ``https://api.telegram.org/bot<token>/sendMessage`` 에 POST.
Telegram 단일 메시지 한도(4096 chars)를 넘으면 청크로 분할해 순차 전송한다.
markdown 이스케이프 이슈 회피를 위해 parse_mode 미지정(plain text)으로 보낸다.

Required env:
    TELEGRAM_BOT_TOKEN — Bot API 토큰 (G21 secret — SECRET_ENV_KEYS 등록)
    TELEGRAM_CHAT_ID   — 발송 대상 chat id (G21 secret)
"""

from __future__ import annotations

import urllib.parse
import urllib.request
from typing import Any

from infrastructure._common.utils import secret_safe_log
from infrastructure.notify.adapter import AdapterResult, NotifierAdapter

# Telegram sendMessage 본문 한도 4096 — 안전 마진 두고 4000 으로 분할.
CHUNK_SIZE = 4000
_HTTP_TIMEOUT_SEC = 30


def _chunk_text(text: str, size: int = CHUNK_SIZE) -> list[str]:
    """text 를 size 단위 청크 list 로 분할 (빈 텍스트는 단일 빈 청크 아님 — 최소 1개)."""
    if not text:
        return [""]
    return [text[i : i + size] for i in range(0, len(text), size)]


class TelegramAdapter(NotifierAdapter):
    name = "telegram"
    required_env = ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID")

    def render(self, brief_md: str) -> dict[str, Any]:
        chunks = _chunk_text(brief_md)
        return {
            "chat_id": (self.env.get("TELEGRAM_CHAT_ID") or "").strip(),
            "chunks": chunks,
            "_total": len(chunks),
        }

    def send(self, payload: dict[str, Any], *, dry_run: bool) -> AdapterResult:
        if dry_run:
            return AdapterResult(
                channel=self.name,
                status="skipped",
                payload=payload,
                skip_reason="dry_run",
            )
        token = (self.env.get("TELEGRAM_BOT_TOKEN") or "").strip()
        chat_id = payload["chat_id"]
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        try:
            for chunk in payload["chunks"]:
                data = urllib.parse.urlencode(
                    {"chat_id": chat_id, "text": chunk}
                ).encode("utf-8")
                req = urllib.request.Request(url, data=data, method="POST")
                with urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT_SEC) as resp:
                    resp.read()
        except Exception as exc:  # noqa: BLE001
            return AdapterResult(
                channel=self.name,
                status="error",
                payload=payload,
                error=secret_safe_log(str(exc), self.env),
            )
        return AdapterResult(channel=self.name, status="sent", payload=payload)


__all__ = ["TelegramAdapter"]
