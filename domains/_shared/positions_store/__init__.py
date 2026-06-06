"""domains/_shared/positions_store — 보유 포지션 thesis.json Contract (공유 커널).

보유 포지션은 risk_engine 사유물이 아니다 — ``thesis`` (falsifier spec) 는
stage4-thesis-auditor skill + 사용자가 *저작*하고, risk_engine 의 일별 monitor 3종
(falsifier_proximity / thesis_expiry_monitor / event_falsifier_linker)가 *소비*한다.
≥2 owner 가 공유하는 multi-owner 스토어이므로 ``_shared`` tier 에 둔다(rule-of-three).
스토어 레이아웃 SSoT: ``telemetry/positions/README.md``.

- ``schema.PositionThesis`` — {ticker, falsifier{category, spec}, time_horizon_months,
  edge_source, asymmetry_score, ...} + ``ThesisProvenance``. frozen + 관용적 ``__post_init__``.
- ``serde`` — dict ↔ dataclass. on-disk thesis.json shape(README §3) + schema/_provenance 메타.
- ``store.PositionsStore`` — load(3 중복 로더 단일 대체) + injected-writer commit. root 주입.

레이어 정책 (``domains/_shared/__init__.py`` 계승, profile_registry 와 동형):
- ``infrastructure`` import 금지 — path root / ``write_output_safely`` 는 caller
  (risk_engine 의 ``_boundary``)가 주입. 본 패키지는 JSON 읽기에 stdlib ``json`` 만 사용.
- 다른 도메인(risk_engine / screener / ...) import 금지 — 본 패키지가 그들의 의존.
"""
from __future__ import annotations
