"""tests/unit/test_notify_dispatcher.py — dispatcher 기본 채널 / registry (ADR-0017).

기본 활성 채널이 email,telegram 으로 전환됐고(slack/gmail 은 옵션 보존), 새 어댑터가
registry 에 등록됐는지 검증한다.
"""

from __future__ import annotations

import pytest

from infrastructure.notify import REGISTRY
from infrastructure.notify.dispatcher import _resolve_channels, dispatch_brief

pytestmark = pytest.mark.unit


def test_default_channels_email_telegram() -> None:
    assert _resolve_channels(None, {}) == ["email", "telegram"]


def test_env_channels_override() -> None:
    assert _resolve_channels(None, {"NOTIFY_CHANNELS": "slack,gmail"}) == [
        "slack",
        "gmail",
    ]


def test_explicit_channels_take_precedence() -> None:
    assert _resolve_channels(["telegram"], {"NOTIFY_CHANNELS": "email"}) == ["telegram"]


def test_registry_contains_all_channels() -> None:
    for ch in ("email", "telegram", "slack", "gmail", "kakao", "discord", "webhook"):
        assert ch in REGISTRY


def test_dispatch_default_channels_skip_when_env_missing(monkeypatch) -> None:
    for k in (
        "NOTIFY_CHANNELS",
        "SMTP_HOST",
        "SMTP_PORT",
        "SMTP_USERNAME",
        "SMTP_PASSWORD",
        "NOTIFY_EMAIL_TO",
        "NOTIFY_EMAIL_FROM",
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_CHAT_ID",
    ):
        monkeypatch.delenv(k, raising=False)
    results = dispatch_brief("# Brief\n\nbody", env={})
    assert set(results) == {"email", "telegram"}
    assert results["email"].status == "skipped"
    assert results["telegram"].status == "skipped"
