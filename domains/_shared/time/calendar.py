"""KRX 거래일 wrapper. holiday JSON SSoT 는 infrastructure/_common 위임.

원래 ``domains/screener/time/calendar.py`` 에 정의되어 있던 helper 를
2026-05-17 에 본 모듈로 이전. 도메인 공유 원시 — 자체 거래일 로직 구현 금지.
"""
from __future__ import annotations

from datetime import date, timedelta

from infrastructure._common.utils import is_trading_day as _is_trading_day_str


def is_trading_day(d: date) -> bool:
    """``d`` 가 KRX 거래일이면 True. ``infrastructure._common.utils`` 의 string
    기반 helper 를 date object 시그너처로 wrap."""
    return _is_trading_day_str(d.isoformat())


def previous_trading_day(d: date) -> date:
    """``d`` 직전의 KRX 거래일 (``d`` 자체 미포함). 휴일/주말 skip."""
    cursor = d - timedelta(days=1)
    while not is_trading_day(cursor):
        cursor -= timedelta(days=1)
    return cursor


def is_today_trading_day(d: date) -> bool:
    """``d`` 가 KRX 거래일이면 True (``is_trading_day`` 별칭)."""
    return is_trading_day(d)
