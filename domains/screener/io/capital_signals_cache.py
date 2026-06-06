"""Capital allocation signals 시계열 cache.

V4 cache 의 ``capital_signals_events`` 키 read/write. clock 시점 가시 events 만
caller 에 반환 — 백테스트 결정론 single point.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from domains.screener._boundary import KST
from domains._shared.time.clock import AsOfClock


def filter_visible_signals(
    events: list[dict[str, Any]],
    clock: AsOfClock,
) -> tuple[str, ...]:
    """events 시계열에서 clock 이전 발생한 signal_type 만 추출 + dedup.

    각 event 는 ``{event_datetime: ISO, signal_type: str, ...}`` 형태.
    event_datetime 파싱 실패 시 해당 event 무시 (graceful, 다음 fetch 에서
    자가 치유).
    """
    visible: set[str] = set()
    for e in events:
        ts_raw = e.get("event_datetime")
        sig = e.get("signal_type")
        if not ts_raw or not sig:
            continue
        try:
            ts = datetime.fromisoformat(ts_raw)
        except (TypeError, ValueError):
            continue
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=KST)
        if clock.can_see(ts):
            visible.add(str(sig))
    return tuple(sorted(visible))


def merge_signal_events(
    prev_events: list[dict[str, Any]],
    new_events: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """기존 events + 새 events 의 dedup 병합. (event_datetime, signal_type) key.

    동일 key 의 중복 event 는 1개로 압축 — 새 event 의 metadata 가 우선.
    sorted by event_datetime ascending.
    """
    by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for e in prev_events:
        key = (str(e.get("event_datetime") or ""), str(e.get("signal_type") or ""))
        if key[0] and key[1]:
            by_key[key] = dict(e)
    for e in new_events:
        key = (str(e.get("event_datetime") or ""), str(e.get("signal_type") or ""))
        if key[0] and key[1]:
            by_key[key] = dict(e)
    return sorted(by_key.values(), key=lambda x: x.get("event_datetime", ""))
