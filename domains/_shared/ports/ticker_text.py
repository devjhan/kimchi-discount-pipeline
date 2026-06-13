"""TickerTextSource — ticker → 임베딩 대상 텍스트 seam (순수 typing, infra import 0).

per-ticker semantic 임베딩의 입력 텍스트 출처를 추상화한다 (14-b). production 출처는
DART 사업보고서 "사업의 내용" 본문(``infrastructure/dart``); 수기 큐레이션 출처로 교체/
보강 가능(14-b 추후 확장). kernel/build 는 본 Protocol 에만 의존하고 composition root 가
concrete source 를 주입한다.

graceful: 텍스트 부재 → 빈 문자열 반환 (raise 금지). build 가 빈 텍스트를 skip + warning.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class TickerTextSource(Protocol):
    """ticker → 임베딩 대상 텍스트. 부재 시 빈 문자열 (G8 — 날조 금지)."""

    def text_for(self, ticker: str) -> str:
        """``ticker`` 의 사업 내용 등 임베딩 텍스트. 부재/실패 → ''."""
        ...
