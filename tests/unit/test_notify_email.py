"""tests/unit/test_notify_email.py — Generic SMTP EmailAdapter (ADR-0017).

``EmailAdapter`` 는 cloud routine MCP 없이 stdlib ``smtplib`` 로 로컬 직접 발송한다.
smtplib 는 mock — 외부 SMTP 연결 없이 호출 인자/경로만 검증.
"""

from __future__ import annotations

import email as email_lib
from unittest.mock import patch

import pytest

from infrastructure.notify.email import EmailAdapter

pytestmark = pytest.mark.unit

FULL_ENV = {
    "SMTP_HOST": "smtp.example.com",
    "SMTP_PORT": "587",
    "SMTP_USERNAME": "user@example.com",
    "SMTP_PASSWORD": "supersecretpw",
    "NOTIFY_EMAIL_TO": "to@example.com",
    "NOTIFY_EMAIL_FROM": "from@example.com",
}

BRIEF = "# Daily Brief — 2026-06-18\n\n## Action Required: None\n\n본문 내용\n"


def test_is_ready_missing_env() -> None:
    adapter = EmailAdapter(env={"SMTP_HOST": "x"})
    ready, missing = adapter.is_ready()
    assert ready is False
    assert "SMTP_PASSWORD" in missing


def test_is_ready_full_env() -> None:
    adapter = EmailAdapter(env=dict(FULL_ENV))
    ready, missing = adapter.is_ready()
    assert ready is True
    assert missing is None


def test_render_subject_from_h1() -> None:
    adapter = EmailAdapter(env=dict(FULL_ENV))
    payload = adapter.render(BRIEF)
    assert payload["subject"] == "Daily Brief — 2026-06-18"
    assert payload["body"] == BRIEF
    assert payload["to"] == "to@example.com"
    assert payload["from"] == "from@example.com"


def test_render_subject_fallback_no_h1() -> None:
    adapter = EmailAdapter(env=dict(FULL_ENV))
    payload = adapter.render("본문만 있고 H1 없음")
    assert payload["subject"] == "Daily Brief"


def test_send_dry_run_skips_no_smtp() -> None:
    adapter = EmailAdapter(env=dict(FULL_ENV))
    payload = adapter.render(BRIEF)
    with patch("infrastructure.notify.email.smtplib.SMTP") as m_smtp:
        result = adapter.send(payload, dry_run=True)
    assert result.status == "skipped"
    assert result.skip_reason == "dry_run"
    m_smtp.assert_not_called()


def test_send_starttls_587() -> None:
    adapter = EmailAdapter(env=dict(FULL_ENV))
    payload = adapter.render(BRIEF)
    with patch("infrastructure.notify.email.smtplib.SMTP") as m_smtp:
        server = m_smtp.return_value.__enter__.return_value
        result = adapter.send(payload, dry_run=False)
    assert result.status == "sent"
    m_smtp.assert_called_once()
    server.starttls.assert_called_once()
    server.login.assert_called_once_with("user@example.com", "supersecretpw")
    server.sendmail.assert_called_once()
    args = server.sendmail.call_args.args
    assert args[0] == "from@example.com"
    assert args[1] == ["to@example.com"]
    parsed = email_lib.message_from_string(args[2])
    assert parsed["To"] == "to@example.com"
    assert parsed["From"] == "from@example.com"
    body = parsed.get_payload(decode=True).decode("utf-8")
    assert "본문 내용" in body


def test_send_ssl_465() -> None:
    env = dict(FULL_ENV, SMTP_PORT="465")
    adapter = EmailAdapter(env=env)
    payload = adapter.render(BRIEF)
    with (
        patch("infrastructure.notify.email.smtplib.SMTP_SSL") as m_ssl,
        patch("infrastructure.notify.email.smtplib.SMTP") as m_plain,
    ):
        server = m_ssl.return_value.__enter__.return_value
        result = adapter.send(payload, dry_run=False)
    assert result.status == "sent"
    m_ssl.assert_called_once()
    m_plain.assert_not_called()
    server.starttls.assert_not_called()
    server.login.assert_called_once_with("user@example.com", "supersecretpw")
    server.sendmail.assert_called_once()


def test_send_error_redacts_password() -> None:
    adapter = EmailAdapter(env=dict(FULL_ENV))
    payload = adapter.render(BRIEF)
    with patch("infrastructure.notify.email.smtplib.SMTP") as m_smtp:
        m_smtp.return_value.__enter__.return_value.login.side_effect = RuntimeError(
            "auth failed for supersecretpw"
        )
        result = adapter.send(payload, dry_run=False)
    assert result.status == "error"
    assert "supersecretpw" not in (result.error or "")
    assert "<SMTP_PASSWORD_REDACTED>" in (result.error or "")
