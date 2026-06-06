"""domains/catalyst — Stage 3 Catalyst Event Scan bounded context.

universe / screener 와 isomorphic 한 DDD modular monolith. 구 ``domains/alpha_factory``
(Stage 3) 의 6 detector + 2 fetch helper + NAV 캐시를 BC 골격으로 승격·개명.

- ``detectors/`` — ``CatalystDetector`` plugin (ABC + registry + factory + 6 plugin).
  universe ``sources/`` 패턴 동형.
- ``domain/event.py`` — ``CatalystEvent`` (frozen 산출 값 객체).
- ``application/scan_catalysts.py`` — orchestrator (I/O 無): detector fan-in +
  G15 d_type augment + quality_pass marker + envelope payload 조립.
- ``io/`` — 01/02 타입드 로더 + DART/KIS/Yahoo fetch (구 stage3 helper 흡수) +
  NAV 시계열 캐시 + 03 writer.
- ``config/detectors.yaml`` — 구 ``thresholds.yaml:catalyst.*`` 흡수 + enable/disable.
- ``_boundary.py`` — 외부 의존 단일 게이트.
- ``audit/`` — G7/G15 invariants + ``_shared/audit`` 소비.
- ``main.py`` — ``python -m domains.catalyst.main`` (구 3 CLI step → 1 step).
"""
from __future__ import annotations
