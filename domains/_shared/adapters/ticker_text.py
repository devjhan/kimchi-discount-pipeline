"""Ticker 텍스트 source 구현 (순수, infra import 0).

- ``ManualTickerTextSource`` — 수기 큐레이션 매핑 (14-b 추후 수기 확장 경로). 결정론·감사
  용이. governance/operations 의 큐레이션 텍스트를 caller 가 dict 로 로드해 주입.
- ``DartTickerTextSource`` — DART 사업보고서 "사업의 내용" 본문 (14-b production source).
  vendor 접촉(``infrastructure/dart``)은 *주입된 fetch* 로만 한다 (infra import 0 유지).
- ``CompositeTickerTextSource`` — 우선순위 fallback (예: 수기 우선, 없으면 DART source).

DART 본문 source 의 fetch / corp_index 바인딩은 consumer ``_boundary`` 가 구성해 주입한다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Sequence


@dataclass(frozen=True)
class ManualTickerTextSource:
    """ticker → 큐레이션 텍스트 dict. 부재 → ''."""

    texts: Mapping[str, str] = field(default_factory=dict)

    def text_for(self, ticker: str) -> str:
        return self.texts.get(ticker, "") or ""


@dataclass(frozen=True)
class DartTickerTextSource:
    """ticker → DART 사업보고서 "사업의 내용" 본문 (14-b production source).

    ``fetch`` 는 주입된 corp_code→본문 함수(``_boundary`` 가 ``infrastructure.dart.
    fetch_business_content`` 에 key/날짜창 바인딩). ``corp_index`` 는 6자리 stock_code →
    8자리 corp_code 매핑. 본 adapter 는 *절대 raise 하지 않는다* — 어떤 실패든 '' 반환
    (TickerTextSource 계약 / G8 — 날조 금지, build 가 빈 텍스트 skip).
    """

    fetch: Callable[[str], str]
    corp_index: Mapping[str, str] = field(default_factory=dict)
    max_chars: int = 20000

    def text_for(self, ticker: str) -> str:
        stock_code = ticker.split(":")[-1].strip()
        corp_code = self.corp_index.get(stock_code)
        if not corp_code:
            return ""
        try:
            text = self.fetch(corp_code) or ""
        except Exception:  # noqa: BLE001 — vendor 실패 → '' graceful (raise 금지)
            return ""
        return text[: self.max_chars]


@dataclass(frozen=True)
class CompositeTickerTextSource:
    """여러 source 를 우선순위로 시도, 첫 비어있지 않은 텍스트 반환."""

    sources: Sequence[Any]  # TickerTextSource (구조적)

    def text_for(self, ticker: str) -> str:
        for src in self.sources:
            text = (src.text_for(ticker) or "").strip()
            if text:
                return text
        return ""
