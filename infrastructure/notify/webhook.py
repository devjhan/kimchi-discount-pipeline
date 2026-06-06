"""
infrastructure/notify/webhook.py — Generic outbound webhook adapter (deferred).

임의 outbound webhook URL 로 brief 본문 POST (text/markdown body). 추후 사용자
backend / 자체 chat bot / Notion 등 통합 시 구현.

Required env (구현 시):
    NOTIFY_WEBHOOK_URL  — POST 대상 URL
    NOTIFY_WEBHOOK_AUTH — Authorization header 값 (옵셔널)
"""

from __future__ import annotations

from typing import Any

from infrastructure.notify.adapter import AdapterResult, NotifierAdapter


class WebhookAdapter(NotifierAdapter):
    name = "webhook"
    required_env = ("NOTIFY_WEBHOOK_URL",)

    def render(self, brief_md: str) -> dict[str, Any]:
        raise NotImplementedError(
            "WebhookAdapter is deferred. enable by implementing render+send."
        )

    def send(self, payload: dict[str, Any], *, dry_run: bool) -> AdapterResult:
        return AdapterResult(
            channel=self.name,
            status="skipped",
            skip_reason="adapter_deferred (WebhookAdapter not implemented yet)",
        )


__all__ = ["WebhookAdapter"]
