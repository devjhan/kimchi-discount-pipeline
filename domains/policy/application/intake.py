"""intake — 이벤트(공시 / 외부신호) → Trigger tuple. 순수 변환 (LLM·I/O 없음).

DART 공시 / ``telemetry/external_signals/`` (ingest-external-signal SOP 산출) 의
raw 를 _boundary 가 dict 로 모아 본 함수에 전달. 빈 입력 = 빈 tuple (Default
No-Action 정상).
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping

from domains.policy.domain.trigger import Trigger


def build_triggers(events: Iterable[Mapping[str, Any]], *, now_iso: str) -> tuple[Trigger, ...]:
    """이벤트 dict iterable → Trigger tuple.

    각 event 는 ``{kind, ticker, payload_ref}`` 필요. 불완전 event 는 skip
    (조용히 — 빈 입력/불완전 입력 모두 Default No-Action). raw payload 직접
    ingest 금지 — payload_ref(공시 rcept_no / 신호 파일 경로) 만 보관 (G10).
    """
    out: list[Trigger] = []
    for e in events:
        kind = e.get("kind")
        ticker = e.get("ticker")
        ref = e.get("payload_ref")
        if not (kind and ticker and ref):
            continue
        out.append(
            Trigger(
                kind=str(kind),
                ticker=str(ticker),
                payload_ref=str(ref),
                detected_at=now_iso,
            )
        )
    return tuple(out)
