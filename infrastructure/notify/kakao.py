"""
infrastructure/notify/kakao.py — KakaoTalk adapter (deferred).

KakaoTalk Business API / 채널 메시지 송신은 OAuth + 추가 plugin 인가가 필요.
구현 시 access token 주입 (`NOTIFY_KAKAO_ACCESS_TOKEN`) + send_to_me 또는
talk_message API endpoint 호출.

본 stub 은 인터페이스만 등록 — 활성화 시 render/send 구현으로 교체.
"""

from __future__ import annotations

from typing import Any

from infrastructure.notify.adapter import AdapterResult, NotifierAdapter


class KakaoAdapter(NotifierAdapter):
    name = "kakao"
    required_env = ("NOTIFY_KAKAO_ACCESS_TOKEN",)

    def render(self, brief_md: str) -> dict[str, Any]:
        raise NotImplementedError(
            "KakaoAdapter is deferred. enable by implementing render+send."
        )

    def send(self, payload: dict[str, Any], *, dry_run: bool) -> AdapterResult:
        return AdapterResult(
            channel=self.name,
            status="skipped",
            skip_reason="adapter_deferred (KakaoAdapter not implemented yet)",
        )


__all__ = ["KakaoAdapter"]
