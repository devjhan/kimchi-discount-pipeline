"""domains/_shared — 도메인 공유 kernel (원시 타입 + cross-cutting 계약).

bounded context (screener / universe / macro / catalyst / risk_engine / policy /
audit_integrity) 사이에서 *반복 등장하는 platform-grade* 원시 + 계약을 포함.
도메인 룰 / business logic 절대 금지.

## 구성

- ``time/`` — AsOfClock + KRX calendar (시점 1급 시민)
- ``profile_registry/`` · ``positions_store/`` — Enrich-Cutoff profile / positions thesis 스토어
- ``audit/`` — G7 citation / GuardViolation / ViolationLog 공유 원시 (per-BC ``audit/`` 소비)
- ``ports/`` — cross-cutting Protocol (CitationPort / ClockPort / DisclosureSourcePort) — 순수 typing
- ``adapters/`` — 주입형 shared 알고리즘 (disclosure_scan) — infra import 0 (port 로만 외부 접촉)
- ``brief_gate/`` — Stage 6 brief 입력 validator (F-19 강등: 구 ``domains/brief_gate`` BC.
  ``_boundary`` 없는 순수 cross-cutting 검증이라 _shared 거주)

## "audit" 명명 disambiguation (catch #7 — rename 없이 문서로 구분)

코드베이스에 "audit" 가 **3 의미**로 등장 — 혼동 방지:
1. ``domains/audit_integrity/`` — **BC**. 4-tier shadow portfolio (paper-trade) 분기 outcome 감사.
2. ``domains/<bc>/audit/`` — per-BC **in-stage 검증 기록** (citation/GuardViolation/ViolationLog,
   stage 실행 중 위반 append). screener/universe/macro/policy/catalyst 보유.
3. ``domains/_shared/audit/`` — 위 (2) 가 공유하는 **kernel 원시** (CITATION_RE / ViolationLog 단일 출처).

레이어 정책:
- _shared 는 ``infrastructure/_common/`` (platform-wide utility — KST 상수, 거래일 캘린더,
  citation 포맷터 등) 를 import 할 수 있다.
- _shared 는 ``infrastructure/dart``, ``infrastructure/kis``, ``infrastructure/yahoo``,
  ``infrastructure/fred`` 등 *vendor-specific adapter* 를 import 하면 안 된다 — BC _boundary 책임.
- _shared 는 다른 도메인 (``domains.screener``, ``domains.universe`` 등) 을 import 하면 안 된다 —
  _shared 가 그들의 dependency 이지 그 반대 아님.

신규 추가 기준:
- 정확히 한 도메인에서만 사용 → 해당 도메인 패키지 내부에 두기
- 두 도메인이 비슷한 코드 → 보수적으로 복제 (3번째 consumer 등장 시 본 패키지로 추출 결정)
- 세 도메인 이상에서 동일 추상 → 본 패키지 추가 후보
"""
from __future__ import annotations
