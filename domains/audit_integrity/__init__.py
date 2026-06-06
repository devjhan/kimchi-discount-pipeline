"""domains/audit_integrity — 4-tier shadow portfolio benchmark bounded context.

통계적 정직성(5번째 사상) 핵심 인프라. Index / Mechanical / LLM-Filtered / Random
4-tier paper portfolio 의 일별 state 를 *결정론 코드*로 갱신해 LLM filter 의 부가가치를
분기 단위로 측정 가능하게 한다 (paper trade only — 자본 이동/broker 호출 0, G9).

- ``domain/`` — Holding / TierState / ShadowPortfolioState 값 객체 + 순수 규칙(state/rules).
- ``application/run_daily_update`` — 4-tier 일별 엔진 (I/O 無, 가격 주입).
- ``io/`` — trail 로더(03/05/05c/01∩02) · state store(atomic) · 가격 source(KIS/Yahoo) · trade-log CSV.
- ``_boundary.py`` — 외부 의존 단일 게이트. ``audit/`` — _shared/audit 소비.
- ``main.py`` — ``python -m domains.audit_integrity.main`` (일별, 구 LLM 스킬 회수 F-6).
- ``init_shadow_state.py`` — state ``--init`` 템플릿 (잔존). ``stat_tests.py`` — 순수 통계 lib
  (investment-audit-outcome 스킬이 분기 비교/self-disable 에 소비, import 경로 보존).
"""
from __future__ import annotations
