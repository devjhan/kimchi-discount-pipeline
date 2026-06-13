"""domains/_shared/policy_profile — scope-tagged 통합 정책 프로파일 Contract (공유 커널, ADR-0013 Q2).

세 legacy 정책 스키마를 ``scope ∈ {global, segment, ticker}`` 단일 ``policy-profile-v1``
스키마로 수렴한다:

- per-ticker  ``enrich-cutoff-profile-v1`` → scope=ticker
- segment     ``segment-profile-v1``       → scope=segment
- global      ``screener-profile-v1``       → scope=global

본 패키지가 **on-disk 스키마/serde 의 단일 권위** 다. ``profile_registry`` /
``segment_registry`` 의 serde 는 본 패키지에 위임하고, 자신의 in-memory view 타입
(``EnrichCutoffProfile`` / ``PolicyContribution``)으로 투영한다 (ADR-0013 결정 2).

cutoff_rules 의 *의미*(metric_path / op 등)는 검증하지 않는다 — 룰 검증의 단일 권위는
screener ``RuleFactory`` (anchor #1, bc-independence 유지). 본 패키지는 shape 만 검증.

레이어 정책 (``domains/_shared/__init__.py`` 계승): ``infrastructure`` 미import (path
helper 는 caller 주입), 타 도메인(screener/universe/policy) 미import.
"""
from __future__ import annotations
