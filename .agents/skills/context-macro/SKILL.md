---
name: context-macro
description: Investment 파이프라인 `domains/macro/` BC 작업 시 domain context 주입. common/ 통합 가이드 파일을 선행 읽기로 안내. 작업 전 invoke 권장.
---

# context-macro

`domains/macro/` BC (Stage 0 Macro Regime Gate) 코드 작업 전 invoke. common/ 디렉토리에 흡수된 내용을 읽으면 원본 파일 참조가 대체된다.

## 선행 읽기

### 공통 (common/)
1. `common/overview.md` — BC 개요, 패키지 구조, 4 Signal 목록, 외부 연결점 테이블, DDD 규약, 검증 명령
2. `common/indicators.md` — Signal 플러그인: ABC, registry, factory, 4 indicator 상세 (fetch + vote)
3. `common/classify.md` — regime 분류: `classify_regime` max-severity aggregate, `detect_regime_shift` backward scan, envelope schema
4. `common/boundaries.md` — DDD 경계: `_boundary.py` 게이트, infra import 규칙, export 함수 카탈로그
5. `common/audit.md` — 검증·로깅: G7 citation 형식 invariant, G6 보장, JSONL violation log, severity 정책
6. `common/config-contract.md` — Config 계약: regimes.yaml 구조, cash_band schema, envelope contract, thresholds.yaml 분리

## 핵심 불변식

- **FRED 지표 fetch 실패 시 `null` → `regime=unknown`** — 추정으로 채워넣기 절대 금지 (D-CORE-3: Default No-Action)
- **Helper 결정론 분류 불변** — `classify_regime` 의 numeric regime 분류는 skill (`stage0-regime-labeler`) 이 절대 변경하지 않음; skill 은 narrative 만 추가
- **`cash_band` 범위 외 조정 금지** — `config/regimes.yaml` 의 `cash_band` 정의를 벗어난 수동 override 금지
- **`_boundary.py` 단일 게이트** — 다른 macro 모듈은 `infrastructure.*` / `os.environ` 직접 사용 금지, `domains._shared.*` (AsOfClock / KRX calendar) 만 예외

## 전형적 실패 패턴

- 지표 부재 시 추측으로 채우기: FRED 지표 1개 누락 → 전체 regime 을 mid 로 가정하고 진행 (금지 — `unknown` 으로 남기고 `warnings` 추가)
- Narrative → deterministic override: LLM narrative 가 helper 의 numeric 분류를 덮어쓰려는 시도 (금지 — narrative 는 별도 `00-macro-regime-narrative.md` 에만)
- Signal 플러그인 미등록: 새 `signals/*.py` 작성 후 `factory.py` import 누락 → registry 에서 발견 안 됨

## 산출물

- `$TRAIL_TODAY/00-macro-regime.json` — 결정론 regime 분류 (schema `stage0-macro-regime-v1`)
- `$TRAIL_TODAY/00-macro-regime-narrative.md` — LLM 보조 narrative (옵셔널, skill `stage0-regime-labeler` 산출)
- `$EXTERNAL_SIGNALS_MACRO_BREADTH_PATH` — SPX breadth prefetch (Stage 0a)
- `$AUDIT_DIR/violations/macro/{date}.jsonl` — violation log (append-only)

## Out of Scope

- 다른 BC 의 책임 — screener / catalyst / risk_engine import 금지 (cross-BC 호출은 `_boundary.py` 게이트 통과)
- Stage 0a SPX breadth auto-fetch (`breadth_fetch.py`) 의 세부 구현 — 별도 모듈
- `config/regimes.yaml` threshold 값 결정 — governance policy 영역
