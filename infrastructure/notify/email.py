"""
infrastructure/notify/email.py — Generic SMTP email adapter.

브리프를 임의 SMTP 서버로 **로컬에서 직접 발송**한다 (cloud routine MCP 불필요).
ADR-0017 — local direct notify.

기존 ``gmail`` adapter (MCP ``create_draft`` 위임) 와 달리 본 adapter 는
stdlib ``smtplib`` 로 send() 안에서 직접 송신한다. SMTP_PORT 가 465 이면
SMTP_SSL, 그 외(기본 587)는 STARTTLS.

Required env:
    SMTP_HOST         — SMTP 서버 호스트 (예: smtp.gmail.com)
    SMTP_PORT         — 포트 (587=STARTTLS / 465=SSL)
    SMTP_USERNAME     — SMTP 인증 사용자
    SMTP_PASSWORD     — SMTP 인증 비밀번호 (G21 secret — SECRET_ENV_KEYS 등록)
    NOTIFY_EMAIL_TO   — 수신 주소
    NOTIFY_EMAIL_FROM — 발신 주소
"""

from __future__ import annotations

import smtplib
from email.mime.text import MIMEText
from typing import Any

from infrastructure._common.utils import secret_safe_log
from infrastructure.notify.adapter import AdapterResult, NotifierAdapter

DEFAULT_SMTP_PORT = 587
_SMTP_TIMEOUT_SEC = 30


class EmailAdapter(NotifierAdapter):
    name = "email"
    required_env = (
        "SMTP_HOST",
        "SMTP_PORT",
        "SMTP_USERNAME",
        "SMTP_PASSWORD",
        "NOTIFY_EMAIL_TO",
        "NOTIFY_EMAIL_FROM",
    )

    def render(self, brief_md: str) -> dict[str, Any]:
        # subject = brief 의 첫 H1 ('# ...'), 없으면 'Daily Brief'.
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
        }

    def send(self, payload: dict[str, Any], *, dry_run: bool) -> AdapterResult:
        if dry_run:
            return AdapterResult(
                channel=self.name,
                status="skipped",
                payload=payload,
                skip_reason="dry_run",
            )
        try:
            host = (self.env.get("SMTP_HOST") or "").strip()
            port = int((self.env.get("SMTP_PORT") or DEFAULT_SMTP_PORT))
            username = (self.env.get("SMTP_USERNAME") or "").strip()
            password = self.env.get("SMTP_PASSWORD") or ""

            msg = MIMEText(payload["body"], "plain", "utf-8")
            msg["Subject"] = payload["subject"]
            msg["From"] = payload["from"]
            msg["To"] = payload["to"]

            if port == 465:
                with smtplib.SMTP_SSL(host, port, timeout=_SMTP_TIMEOUT_SEC) as server:
                    server.login(username, password)
                    server.sendmail(
                        payload["from"], [payload["to"]], msg.as_string()
                    )
            else:
                with smtplib.SMTP(host, port, timeout=_SMTP_TIMEOUT_SEC) as server:
                    server.starttls()
                    server.login(username, password)
                    server.sendmail(
                        payload["from"], [payload["to"]], msg.as_string()
                    )
        except Exception as exc:  # noqa: BLE001
            return AdapterResult(
                channel=self.name,
                status="error",
                payload=payload,
                error=secret_safe_log(str(exc), self.env),
            )
        return AdapterResult(channel=self.name, status="sent", payload=payload)


__all__ = ["EmailAdapter"]
