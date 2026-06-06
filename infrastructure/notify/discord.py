"""
infrastructure/notify/discord.py — Discord adapter (deferred).

Discord Webhook 으로 송신. 구현 시 stdlib urllib 로
`https://discord.com/api/webhooks/<id>/<token>` POST. payload 는 `{content: str}`
또는 embed dict.

Required env (구현 시):
    NOTIFY_DISCORD_WEBHOOK_URL — Discord 채널 webhook URL (secret)

본 stub 은 인터페이스만 등록.
"""

from __future__ import annotations

from typing import Any

from infrastructure.notify.adapter import AdapterResult, NotifierAdapter


class DiscordAdapter(NotifierAdapter):
    name = "discord"
    required_env = ("NOTIFY_DISCORD_WEBHOOK_URL",)

    def render(self, brief_md: str) -> dict[str, Any]:
        raise NotImplementedError(
            "DiscordAdapter is deferred. enable by implementing render+send."
        )

    def send(self, payload: dict[str, Any], *, dry_run: bool) -> AdapterResult:
        return AdapterResult(
            channel=self.name,
            status="skipped",
            skip_reason="adapter_deferred (DiscordAdapter not implemented yet)",
        )


__all__ = ["DiscordAdapter"]
