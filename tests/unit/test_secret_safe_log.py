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
