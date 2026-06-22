---
name: context-universe
description: domains/universe/ (Stage 1) 코드 읽기/수정 전 반드시 로드. 미로드 시 universe 구성·fan-in·enrich·manual_additions 불변식 위반 확정. common/ 통합 가이드 선행 읽기 안내 포함.
---

# context-universe

`domains/universe/` BC (Stage 1 Universe Fan-in + Enrich) 코드 작업 전 invoke. common/ 디렉토리에 흡수된 내용을 읽으면 원본 파일 참조가 대체된다.

## 선행 읽기

### 공통 (common/)
1. `common/overview.md` — BC 개요, 4 Anchor, 패키지 구조, 외부 연결점 테이블, DDD 규약, 검증 명령
2. `common/sources.md` — DiscoverySource plugin: ABC, 6 source 카탈로그, registry/factory, 신규 추가 절차
3. `common/enrichers.md` — Enricher plugin: ABC, 2 enricher 카탈로그, applies_to 매칭, G6 보장
4. `common/boundaries.md` — DDD 경계: `_boundary.py` 게이트, infra import 규칙, export 함수 카탈로그, 절대 금지 패턴
5. `common/audit.md` — 검증·로깅: G6/G7/G14 invariants, ViolationLog 구조, severity 정책
6. `common/config-contract.md` — Config 계약: schema 헤더, 6 config 파일 카탈로그, sub-config 분리, spec 패턴

## 핵심 불변식

- **`manual_additions` 만 새 종목 추가 (G14)** — 자동 종목 추가 로직 절대 금지; universe 는 입력 단계
- **Enricher registry name 만 사용** — 미등록 enricher name 으로 호출 시 `KeyError` → 정상 방어 실패
- **`source_category` enum 벗어나지 않기** — `UniverseEntry.source_category` 는 정의된 enum 값만 (`manual`, `dart_disclosure`, `holding_company`, `preferred_pair_seed`)
- **Shared `disclosure_scan` (F-16)**: `DartDisclosureFilter` 의 per-item 매칭/dedup 스켈레톤은 `domains/_shared/adapters/disclosure_scan` 으로 추출 — catalyst 와 공유

## 전형적 실패 패턴

- DART fetch 실패 시 cache 없는 ticker 누락: 정상 동작 — `warnings` 에 기록하고 skip, fallback 으로 채워넣기 금지
- Enricher 미등록 name 사용: `config/enrichers.yaml` 에 없는 name 을 `required_enrichments` 로 지정 → 런타임 오류
- 다른 BC 의 내부 객체 import: `domains/screener/domain/...` 등 직접 import → DDD 경계 위반 (산출 파일 + envelope schema 만 인용)

## 산출물

- `$TRAIL_TODAY/01-universe.json` — universe 종목 리스트 + enrich 결과 (envelope schema `stage1-universe-v1`)
- `$AUDIT_DIR/violations/universe/{date}.jsonl` — G6/G7/G14 위반 로그 (JSONL append-only)
- stdout handoff 1줄: `[stage1-universe] verdict=... items=N -> $TRAIL_TODAY/01-universe.json`

## Out of Scope

- 다른 BC 의 책임 (screener / catalyst / risk_engine) — cross-BC 호출은 `_boundary.py` 게이트 통과
- `governance/thresholds.yaml.universe.*` — legacy, `domains/universe/config/*.yaml` 로 완전 이전됨
- NAV discount / spread zscore 정량 계산 상세 — enricher plugin 내부 구현
