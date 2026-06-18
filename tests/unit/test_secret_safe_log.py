"""tests/unit/test_secret_safe_log.py — G21 secret redaction (ADR-0016).

``DEEPSEEK_API_KEY`` 는 claude-cli-deepseek adapter 가 자식 프로세스 env(ANTHROPIC_AUTH_TOKEN)
로 주입하는 live secret 이므로, ``SECRET_ENV_KEYS`` 에 포함되어 로그 redaction 대상이어야 한다.
"""

from __future__ import annotations

import pytest

from infrastructure._common.utils import SECRET_ENV_KEYS, secret_safe_log

pytestmark = pytest.mark.unit


def test_deepseek_api_key_in_secret_env_keys() -> None:
    assert "DEEPSEEK_API_KEY" in SECRET_ENV_KEYS


def test_secret_safe_log_redacts_deepseek_key() -> None:
    env = {"DEEPSEEK_API_KEY": "sk-deepseek-verysecret-123"}
    msg = "calling backend with key sk-deepseek-verysecret-123 ok"
    redacted = secret_safe_log(msg, env)
    assert "sk-deepseek-verysecret-123" not in redacted
    assert "<DEEPSEEK_API_KEY_REDACTED>" in redacted


def test_secret_safe_log_noop_when_key_absent() -> None:
    env = {"DEEPSEEK_API_KEY": ""}
    msg = "no secret here"
    assert secret_safe_log(msg, env) == "no secret here"


def test_notify_secrets_in_secret_env_keys() -> None:
    # ADR-0017 — email(SMTP) / telegram 로컬 직접 발송 secret 은 redaction 대상.
    assert "SMTP_PASSWORD" in SECRET_ENV_KEYS
    assert "TELEGRAM_BOT_TOKEN" in SECRET_ENV_KEYS
    assert "TELEGRAM_CHAT_ID" in SECRET_ENV_KEYS


def test_secret_safe_log_redacts_smtp_password() -> None:
    env = {"SMTP_PASSWORD": "app-pw-secret-xyz"}
    msg = "smtp auth failed for app-pw-secret-xyz"
    redacted = secret_safe_log(msg, env)
    assert "app-pw-secret-xyz" not in redacted
    assert "<SMTP_PASSWORD_REDACTED>" in redacted


def test_secret_safe_log_redacts_telegram_token() -> None:
    env = {"TELEGRAM_BOT_TOKEN": "123:ABCsecrettoken"}
    msg = "POST https://api.telegram.org/bot123:ABCsecrettoken/sendMessage failed"
    redacted = secret_safe_log(msg, env)
    assert "123:ABCsecrettoken" not in redacted
    assert "<TELEGRAM_BOT_TOKEN_REDACTED>" in redacted
