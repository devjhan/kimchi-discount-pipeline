"""domains/_shared/segment_registry — 부분집합(segment) profile 계층 Contract (공유 커널).

per-ticker(``profile_registry``)와 whole-universe(screener strategy) 사이의 *빈 중간
tier* 를 채운다: **선언적·계층적·합성적으로 가른 부분집합** 에 enrich-cutoff 정책을
참조(attach)한다 (selector-only, 1-b). selector 의 leaf 는 rule-based(``threshold``,
선택 속성 namespace)와 semantic(``semantic_similarity``, 임베딩 cosine)이 **동급** 이다.

- ``attributes`` — 선택 속성 namespace 화이트리스트 (5-a, screener metric_path 와 분리).
- ``concepts`` — ConceptDeclaration + ConceptRegistry (semantic anchor 의 선언 SSoT, 9-a).
- ``selector`` — SelectorEngine, 3-값 논리 멤버십 (G8/G11 — 의미 불명을 멤버로 강제 안 함).
- ``schema`` / ``serde`` / ``registry`` — SegmentDefinition + versioned read (G20).
- ``merge`` — MergeEngine, 명시적 per-field 합성 + 계층 override (6-a).
- ``resolver`` — SegmentResolver.resolve(ticker) → EnrichCutoffProfile (synthesized).

레이어 정책 (``domains/_shared/__init__.py`` 계승):
- ``infrastructure._common`` (stdlib utility) 만 import 허용. vendor adapter
  (dart/kis/yahoo/fred) · 타 도메인(screener/universe/...) import 금지.
- 임베딩 / 벡터 저장은 ``_shared/ports`` 의 Protocol(EmbeddingPort / VectorIndexPort)로만
  접촉 — concrete adapter 는 ``infrastructure/`` 거주, caller 가 주입 (D-ARCH-4).

⚠️ ``profile_registry`` (per-ticker) 와 혼동 금지 — 본 커널은 그 *상위 합성 계층* 이다.
``governance/`` (선언 SSoT: segments/ + concepts/) 가 본 커널의 입력이고, 벡터 인덱스
(telemetry, 모델 버전 증거)는 파생 산출이다.
"""
from __future__ import annotations
