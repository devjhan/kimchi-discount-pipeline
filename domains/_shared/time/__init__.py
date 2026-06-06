"""domains/_shared/time — 시점 / 거래일 공유 원시.

- ``clock.AsOfClock`` — tz-aware 시점 single source. 백테스트 lookahead bias
  차단의 핵심 객체.
- ``calendar.previous_trading_day`` / ``is_today_trading_day`` — KRX 거래일
  helper. holiday JSON SSoT 는 infrastructure/_common 위임.

도메인은 본 모듈을 직접 import 한다 (각 도메인의 _boundary 를 통하지 않음).
근거: 이 두 객체는 행동 (외부 IO) 가 없는 pure value/utility — anti-corruption
layer 가 필요 없는 원시 타입에 해당. AsOfClock 인스턴스의 비교 / 정렬 / 해시
가 도메인 경계를 넘어 일관성을 가져야 하기 때문에 single class definition 이
필수.
"""
from __future__ import annotations
