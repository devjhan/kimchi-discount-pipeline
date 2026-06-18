"""
infrastructure/notify — outbound 알림 어댑터 registry.

브리프를 외부 채널(Slack/Gmail/Telegram/Discord/Kakao/Webhook)로 내보내는 outbound
I/O 어댑터 묶음. ``infrastructure/dart``·``kis``·``yahoo`` 와 동형 — 저장소의
"infrastructure = 외부 I/O 격리" 룰에 따라 ``domains/`` 가 아닌 여기에 둔다.

활성 채널 = REGISTRY 의 key. ``dispatcher`` 는 NOTIFY_CHANNELS env 와 본 registry 의
교집합을 실행. 새 채널 추가는 다음 2 라인:

    from infrastructure.notify.kakao import KakaoAdapter
    REGISTRY["kakao"] = KakaoAdapter

deferred adapter 도 미리 등록되어 있으나, render/send 가 NotImplementedError
(deferred 문구) 또는 'skipped' 반환만 한다 — dispatcher 가 자연스럽게 noop.
"""

from __future__ import annotations

from infrastructure.notify.adapter import (
    AdapterResult,
    BriefBlocked,
    NotifierAdapter,
)
from infrastructure.notify.discord import DiscordAdapter
from infrastructure.notify.email import EmailAdapter
from infrastructure.notify.gmail import GmailAdapter
from infrastructure.notify.kakao import KakaoAdapter
from infrastructure.notify.slack import SlackAdapter
from infrastructure.notify.telegram import TelegramAdapter
from infrastructure.notify.webhook import WebhookAdapter

REGISTRY: dict[str, type[NotifierAdapter]] = {
    SlackAdapter.name: SlackAdapter,
    GmailAdapter.name: GmailAdapter,
    EmailAdapter.name: EmailAdapter,
    TelegramAdapter.name: TelegramAdapter,
    KakaoAdapter.name: KakaoAdapter,
    DiscordAdapter.name: DiscordAdapter,
    WebhookAdapter.name: WebhookAdapter,
}

__all__ = [
    "REGISTRY",
    "AdapterResult",
    "BriefBlocked",
    "NotifierAdapter",
    "SlackAdapter",
    "GmailAdapter",
    "EmailAdapter",
    "TelegramAdapter",
    "KakaoAdapter",
    "DiscordAdapter",
    "WebhookAdapter",
]
