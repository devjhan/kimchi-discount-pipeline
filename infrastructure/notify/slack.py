"""
infrastructure/notify/slack.py — Slack adapter.

Slack 송신은 Anthropic-managed cloud routine 환경의 Slack MCP connector
(`slack_send_message` tool) 가 담당한다. 본 adapter 는 payload (channel + text)
를 빌드해 routine prompt 에 반환하고, 실제 tool invocation 은 LLM 본체가 한다.

dry_run / connector 미가용 환경에서는 'skipped' status 만 반환.

Required env:
    NOTIFY_SLACK_CHANNEL — 발송 대상 채널 ID (예: C0123456) 또는 #channel-name
"""

from __future__ import annotations

from typing import Any

from infrastructure.notify.adapter import AdapterResult, NotifierAdapter

# Slack 단일 메시지 최대 ~40,000 chars. 초과 시 truncate + '... (truncated)'.
MAX_MESSAGE_CHARS = 38000


class SlackAdapter(NotifierAdapter):
    name = "slack"
    required_env = ("NOTIFY_SLACK_CHANNEL",)

    def render(self, brief_md: str) -> dict[str, Any]:
        text = brief_md
        if len(text) > MAX_MESSAGE_CHARS:
            text = text[:MAX_MESSAGE_CHARS] + "\n\n... (truncated for Slack message limit)"
        channel = (self.env.get("NOTIFY_SLACK_CHANNEL") or "").strip()
        return {
            "channel": channel,
            "text": text,
            "_mcp_tool_hint": "slack_send_message",
        }

    def send(self, payload: dict[str, Any], *, dry_run: bool) -> AdapterResult:
        # dispatcher 가 payload 를 routine prompt 로 노출 — 실제 송신은 routine 의
        # LLM 이 Slack MCP 도구로 수행.  여기서는 검증 + payload 동봉만.
        if dry_run:
            return AdapterResult(
                channel=self.name, status="skipped", payload=payload, skip_reason="dry_run"
            )
        return AdapterResult(channel=self.name, status="sent", payload=payload)


__all__ = ["SlackAdapter"]
