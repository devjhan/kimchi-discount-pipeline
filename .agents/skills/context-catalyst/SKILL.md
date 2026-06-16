---
name: context-catalyst
description: Investment 파이프라인 `domains/catalyst/` BC 작업 시 domain context 주입. common/ 통합 가이드 파일을 선행 읽기로 안내. 작업 전 invoke 권장.
---

# context-catalyst

`domains/catalyst/` BC (Stage 3 Catalyst Event Scan) 코드 작업 전 invoke. common/ 디렉토리에 흡수된 내용을 읽으면 원본 파일 참조가 대체된다.

## 선행 읽기

### 공통 (common/)
1. `common/overview.md` — BC 개요, 4 Anchor, 패키지 구조, 외부 연결점 테이블, DDD 규약, 검증 명령
2. `common/detectors.md` — CatalystDetector plugin: ABC, 6 detector 카탈로그, A/B/D-type taxonomy, registry/factory, 신규 추가 절차
3. `common/scan.md` — Orchestrator: `scan_catalysts` flow, G15 d_type augment/orphan 처리, shared adapter 사용, 실행 순서 고정
4. `common/boundaries.md` — DDD 경계: `_boundary.py` 게이트, infra import 규칙 (절대적), export 함수 카탈로그, `_shared` 예외
5. `common/audit.md` — 검증·로깅: config_build invariant, G7 citation (미연결), ViolationLog, 적용 G-guard 표
6. `common/config-contract.md` — Config 계약: detectors.yaml schema, spec 패턴, 실행 순서 byte-parity, schema bump 규약

## 핵심 불변식

- **6 detector plugin 만 catalyst source** — 새 catalyst 유형 추가 시 `detectors/{name}.py` (`@register_detector`) + `factory.py` import + `config/detectors.yaml` 한 줄
- **`d_type` 단독 trigger 금지 (G15)** — activist 5% 는 A-type/B-type 과 결합되어야 trigger (augment-only); orphan d_type → `warnings` 기록
- **`trigger_class` 오분류 금지** — A-type(자사주소각/분할/NAV축소), B-type(인덱스편출/어닝패닉), D-type(행동주의) 분류 엄격
- **Shared `disclosure_scan` (F-16)**: DART 3 detector (treasury/spin_off/activist) 는 `domains/_shared/adapters/disclosure_scan` 공유 — 구 3중복제 소멸

## 전형적 실패 패턴

- DART `rcept_no` 없는 event 생성: 공시번호 없이 catalyst event 발행 → citation trace 불가 (금지)
- `a_type` / `b_type` 구분 오류: 자사주 소각을 B-type 으로, 인덱스 편출을 A-type 으로 분류 → downstream thesis-auditor 가 잘못된 edge_source 판단
- Activist 5% 단독 trigger 수용: D-type 만으로 catalyst trigger → G15 위반 (A/B-type 결합 강제)

## 산출물

- `$TRAIL_TODAY/03-catalyst-events.json` — trigger 감지된 catalyst event 리스트 (envelope schema)
- stdout handoff 1줄: `[stage3] verdict=... items=N -> $TRAIL_TODAY/03-catalyst-events.json`
- `$AUDIT_DIR/violations/catalyst/{date}.jsonl` — violation log (JSONL append-only)

## Out of Scope

- 다른 BC 의 책임 — screener / risk_engine / universe 내부 import 금지
- KIS/Yahoo price fetch 상세 — `_boundary` 어댑터 내부 구현
- Thesis 작성 / falsifier 정의 — Stage 4 skill `stage4-thesis-auditor` 책임
