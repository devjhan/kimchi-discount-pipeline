"""domains/universe — Stage 1 universe discovery + enrichment bounded context.

투자 파이프라인 Stage 1 의 fan-in collector + per-source attribute enricher.
한국 특수상황 (지주사 / 우선주 / 분할 / 자사주 소각 / 행동주의 진입) 종목을
N 개 외부 source 에서 발견하고, source_category 별 enricher 가 부가 attribute
(NAV 할인율, 우선주 스프레드 z-score 등) 를 attach 한다.

screener 패키지와 isomorphic 한 DDD 구조 — _boundary.py (anti-corruption layer)
+ AsOfClock (`domains._shared.time.clock`) + audit/ wiring + .guidelines/ 6 markdown.
단 *내부 패턴은 다름*: screener 의 Composite Rule 트리 대신 DiscoverySource plugin
+ Enricher plugin (외부 분석 의 "fan-in collector + vector mapper" 에 적합).

산출물: ``operations/{YYYY-MM-DD}/01-universe.json``
schema: ``investment-stage1-universe-v1``

대체 이력:
<!-- legacy-ok -->
- [Run 4 완료 2026-05-17] ``domains.alpha_factory.universe`` → 본 패키지의 ``main`` +
  ``application.build_universe``. 옛 파일 삭제됨.
- [Run 5 완료 2026-05-17] ``domains.alpha_factory.stage1_nav_calc`` →
  ``enrichers.nav_discount`` + ``domains.alpha_factory.stage1_pref_spread`` →
  ``enrichers.spread_zscore`` + seed source ``sources.preferred_share_pair_seed``.
  옛 파일 모두 삭제됨.
<!-- /legacy-ok -->
"""
from __future__ import annotations
