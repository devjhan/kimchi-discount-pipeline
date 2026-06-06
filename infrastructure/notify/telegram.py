"""
infrastructure/notify/telegram.py — Telegram adapter (deferred).

Telegram MCP connector 가 cloud routine 환경에 없어 현재 1차 도입 미선택.
구현 시 stdlib urllib 로 https://api.telegram.org/bot<token>/sendMessage POST.

Required env (구현 시):
    TELEGRAM_BOT_TOKEN
    TELEGRAM_CHAT_ID
"""

from __future__ import annotations

from typing import Any

from infrastructure.notify.adapter import AdapterResult, NotifierAdapter


class TelegramAdapter(NotifierAdapter):
    name = "telegram"
    required_env = ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID")

    def render(self, brief_md: str) -> dict[str, Any]:
        raise NotImplementedError(
            "TelegramAdapter is deferred. enable by implementing render+send."
        )

    def send(self, payload: dict[str, Any], *, dry_run: bool) -> AdapterResult:
        return AdapterResult(
            channel=self.name,
            status="skipped",
            skip_reason="adapter_deferred (TelegramAdapter not implemented yet)",
        )


__all__ = ["TelegramAdapter"]
