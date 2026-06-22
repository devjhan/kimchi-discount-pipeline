---
name: context-screener
description: domains/screener/ (Stage 2) 코드 읽기/수정 전 반드시 로드. 미로드 시 quality filter·RuleFactory·verdict·G13 불변식 위반 확정. common/ 통합 가이드 선행 읽기 안내 포함.
---

# context-screener

`domains/screener/` BC (Stage 2 Quality Filter) 코드 작업 전 invoke. common/ 디렉토리에 흡수된 내용을 읽으면 원본 파일 참조가 대체된다.

## 선행 읽기

### 공통 (common/)
1. `common/overview.md` — BC 개요, 4 Anchor, 패키지 구조, 외부 연결점 (inbound/outbound/downstream), Ports & Adapters
2. `common/rules.md` — Rule 트리: ABC, leaf/composite/guards, `RuleFactory.build_strategy`, 직접 생성 금지
3. `common/resolver.md` — metric_path 화이트리스트: `register_metric`, 절대 금지 패턴 (eval/getattr), 등록된 metric 목록
4. `common/hard-guards.md` — Hard guard 잠금 영역: 변경 절차, locked_paths, `HardGuardViolationError`, 현재 guards
5. `common/cache-contract.md` — Financial cache: Live vs PointInTime, clock.can_see boundary, v4 schema, TTL/grace
6. `common/boundaries.md` — DDD 경계: `_boundary.py` 게이트, Ports & Adapters 패턴, export 함수, `_shared` 예외

## 핵심 불변식

- **Quality filter 절대 우회 금지 (G13)** — `verdict=fail` 종목은 어떤 경로로도 downstream 진입 불가
- **Rule tree only** — 임의 threshold 추가 금지, 모든 cutoff 는 `RuleFactory.build_strategy` 트리 내에서만 정의
- **`cutoff_rules` 의 `metric_path` 는 `methods_manifest` 화이트리스트 내** — 화이트리스트 밖 metric_path 사용 시 런타임 reject
- **`_boundary.py` 단일 게이트** → Ports & Adapters: `application/`·`domain/` 은 `_boundary` import 0, port Protocol 에만 의존

## 전형적 실패 패턴

- Financial cache 부재 시 `unknown` → 바로 fail 처리: 정상 동작 — 데이터 없으면 통과시키지 않음 (false-positive 방지)
- `profile_registry` 미존재 ticker 평가 시도: profile 없이 default 전략으로 fallback → `warnings` 기록
- Resolver 에서 dynamic eval 사용: `eval()` / `getattr()` chain 으로 임의 metric_path 해석 → 화이트리스트 우회 (금지)

## 산출물

- `$TRAIL_TODAY/02-quality-filter.json` — 종목별 verdict + rule 결과 (envelope schema)
- `$TRAIL_TODAY/02-quality-lens.json` — LLM 정성 lens 평가 (옵셔널, skill `stage2-quality-lens` 산출 — `verdict=pass` 종목만)
- `$TRAIL_TODAY/02-fin-fetch.json` — 재무 fetch 상세 (선택적)
- stdout handoff 1줄: `[stage2] verdict=pass items=N -> $TRAIL_TODAY/02-quality-filter.json`

## Out of Scope

- 다른 BC 의 책임 — catalyst / risk_engine / universe 내부 import 금지
- Financial cache prefetch / DART raw data fetch — `io/` 어댑터 내부 구현
- `governance/policy/profiles/{ticker}/` 의 cutoff_rules 작성 — policy BC (`/policy-profiler`) 책임
