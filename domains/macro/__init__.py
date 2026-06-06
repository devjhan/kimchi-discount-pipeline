"""domains/macro — Stage 0 macro regime classifier bounded context.

투자 파이프라인 Stage 0 (Macro Regime Gate) — 4 indicator (yield curve / credit
spread / VIX percentile / SPX breadth) 기반 결정적 regime 분류 (early_cycle /
mid_cycle / late_cycle / crisis / unknown). 분기 cash_band 결정 입력.

screener / universe 와 isomorphic 한 DDD 구조 — _boundary.py + audit/ + config/
+ .guidelines/ + ``signals/`` 플러그인. 각 indicator 는 ``Signal`` (fetch + vote)
플러그인 (``@register_signal``); ``classify_regime`` 은 registry 로 vote 를 조회해
max-severity 만 aggregate. 새 indicator = Signal 1 클래스 + ``config/regimes.yaml``
``signals:`` 한 줄 (F-9 — screener Rule 패턴의 vote-in-signal 롤아웃).

산출물:
- ``$TRAIL_TODAY/00-macro-regime.json`` (envelope schema ``investment-stage0-macro-regime-v1``)
- ``$EXTERNAL_SIGNALS_MACRO_BREADTH_PATH`` (Stage 0a breadth_fetch 가 작성)

대체 이력:
<!-- legacy-ok -->
- [Run 7 완료 2026-05-17] ``domains.risk_engine.macro_regime`` → 본 패키지의
  ``main`` + ``application.regime_classify`` + ``indicators``.
- [Run 7 완료 2026-05-17] ``domains.risk_engine.macro_breadth_fetch`` → 본 패키지의
  ``breadth_fetch``. 옛 파일 모두 삭제.
<!-- /legacy-ok -->
"""
from __future__ import annotations
