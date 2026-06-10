"""
infrastructure/notify/gmail.py — Gmail adapter.

본 adapter 는 to / from / subject / body 페이로드를 빌드한다. 실제 송신은
호출자가 담당한다.

draft 우선 (auto-send 회피) — 호출자가 draft / send 를 결정.

Required env:
    NOTIFY_EMAIL_TO   — 수신 주소
    NOTIFY_EMAIL_FROM — 발신 주소 (Gmail account 자체)
"""

from __future__ import annotations

from typing import Any

from infrastructure.notify.adapter import AdapterResult, NotifierAdapter

# Gmail body 사실상 무제한 — daily brief 는 충분히 들어감.


class GmailAdapter(NotifierAdapter):
    name = "gmail"
    required_env = ("NOTIFY_EMAIL_TO", "NOTIFY_EMAIL_FROM")

    def render(self, brief_md: str) -> dict[str, Any]:
        # subject 첫 줄에 brief 의 첫 H1 를 인용 — 'Daily Brief — YYYY-MM-DD'.
        subject = "Daily Brief"
        for line in brief_md.splitlines():
            if line.startswith("# "):
                subject = line[2:].strip()
                break
        return {
            "to": (self.env.get("NOTIFY_EMAIL_TO") or "").strip(),
            "from": (self.env.get("NOTIFY_EMAIL_FROM") or "").strip(),
            "subject": subject,
            "body": brief_md,
            "_mcp_tool_hint": "create_draft",
        }

    def send(self, payload: dict[str, Any], *, dry_run: bool) -> AdapterResult:
        if dry_run:
            return AdapterResult(
                channel=self.name,
                status="skipped",
                payload=payload,
                skip_reason="dry_run",
            )
        return AdapterResult(channel=self.name, status="sent", payload=payload)


__all__ = ["GmailAdapter"]
