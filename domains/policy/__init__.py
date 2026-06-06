"""domains/policy — 종목별 정책(Enrich-Cutoff 프로파일) 저작 LLM producer BC.

정책/메커니즘 분리에서 **producer** 측. trigger(공시 / 외부신호 / 수동) → LLM
research → 종목별 ``required_enrichments`` + ``cutoff_rules`` 제안 → drift gate →
profile_registry 에 versioned commit. universe/screener(mechanism)는 registry 만
소비하며 policy 를 **절대 동기 호출하지 않는다** — policy 는 자체 launchd 일정의
out-of-band 실행 (저장소에 asyncio 없음; "비동기" = daily batch 와 분리된 일정).

⚠️ ``governance/`` (선언적 정책 specs/config — 입법부) 와 다름. policy 는 종목별
정책을 *저작*하는 엔진. ``domains/_shared/profile_registry/`` (그 산출물의 계약/
저장소) 와도 다름.

DDD 구조 (macro BC isomorphic):
- ``_boundary`` — 외부 의존 단일 게이트 (경로 helper / write / DART / time).
- ``domain/`` — Trigger / ResearchOutput frozen value objects.
- ``ports/llm`` — PolicyEngine Protocol (LLM seam; 구현은 _boundary 뒤).
- ``application/`` — intake(순수) / analyze(engine 위임) / commit(drift gate + versioning).
- ``audit/`` — GuardViolation JSONL log (macro 동형).
- ``main`` — sync CLI.
"""
from __future__ import annotations
