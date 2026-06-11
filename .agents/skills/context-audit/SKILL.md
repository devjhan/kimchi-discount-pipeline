---
name: context-audit
description: Investment 파이프라인 `domains/audit_integrity/` BC 작업 시 domain context 주입. common/ 통합 가이드 파일을 선행 읽기로 안내. 작업 전 invoke 권장.
---

# context-audit

`domains/audit_integrity/` BC (4-tier Shadow Portfolio Audit) 코드 작업 전 invoke. 본문은 인덱스 — 상세는 `common/` 파일 참조.

> ⚠️ **다른 "audit" 스킬과 착각 금지**: `context-audit` 은 `domains/audit_integrity` BC 용 (일별 shadow portfolio NAV 결정론 엔진). `audit-outcome` (분기 수익률 비교) / `audit-process` (주간 규정 위반 집계) 와 다른 concern.

## 선행 읽기

### 공통 (common/)
1. `common/overview.md` — BC 개요, 패키지 구조, 4 Anchor, 4 tier 구성표 (Index/Mechanical/LLM-Filtered/Random), 외부 연결점, CLI, 산출물, "audit" 3중 의미 주의
2. `common/shadow-portfolio.md` — Tier 갱신 orchestration (run_daily_update), holdings 결정 로직, paper-trade record (trade log), NAV/return tracking, PAPER-TRADE-ONLY (G9)
3. `common/stat-tests.md` — stat_tests.py (stdlib only): Welch t-test, bootstrap CI, quarterly_returns, evaluate_self_disable_trigger; sample-size band (4 band); G19 forbidden-language; read-only skill 소비 (ADR-0003)
4. `common/boundaries.md` — `_boundary.py` 게이트, invariant-C/D GREEN (callback 주입 패턴 = reference 사례), KIS/Yahoo 가격 read-only, init_shadow_state.py allowlist
5. `common/audit.md` — ViolationLog (parity-only), G-guard 적용표, 향후 gap
6. `common/config-contract.md` — thresholds.yaml.statistics 키, D-CFG-1, schema bump 규약

## 핵심 불변식

- **Shadow portfolio state read-only** — 갱신은 본 BC 결정론 엔진 (`main.py`) 만 수행; audit skill (`audit-outcome` / `audit-process`) 은 read-only 비교만
- **4-tier 비교 only** — outcome 평가 (분기 누적 수익률 비교) 는 별도 `audit-outcome` skill; 본 BC 는 일별 NAV paper-trade 갱신
- **Self-disable trigger**: tier_2(LLM) < tier_1(Mechanical) 4분기 연속 시 `disable-trigger.json` 발동 — 통계적 정직성 (5대 철학 #5)
- **G9: 실제 broker 호출 0** — paper trade only, KIS price read endpoint 만 사용
- **G6: 모든 정량은 결정론 산식** — NAV / 수익률 계산은 LLM 위임 금지 (F-6 회수 교훈, ADR-0003)

## 전형적 실패 패턴

- Audit-report 덮어쓰기: `shadow-portfolio-state.json` 을 G20 suffix 없이 overwrite → append-only 위반 (`init_shadow_state --force` 만 예외)
- Sample size 미충족 alpha 주장: N<10 인데 "LLM filter outperforms" 같은 주장 → G19 위반 (통계적 정직성)
- Secret 값 audit 본문에 노출: `outcome-{YYYY-Q}.md` / `process-{YYYY-WW}.md` 에 API key 등 raw 값 등장 → D-SEC-1 위반
- "Audit" 명명 혼동: `audit_integrity` (outcome 감사) vs per-BC `<bc>/audit/` (in-stage 검증) vs `_shared/audit/` (kernel 원시) — 3중 의미 구분

## 산출물

- `$AUDIT_DIR/shadow-portfolio-state.json` — 4-tier NAV state (cross-day 누적, 재생성 불가)
- `$AUDIT_DIR/trade-log-{tier}.csv` — tier 별 진입/청산 기록 (4개 파일)
- (read-only outcome skill 산출): `$AUDIT_DIR/outcome-{YYYY-Q}.md` / `$AUDIT_DIR/disable-trigger.json` / `$AUDIT_DIR/process-{YYYY-WW}.md`

## Out of Scope

- 다른 BC 의 책임 — screener / risk_engine / universe 내부 import 금지
- 분기 outcome audit 수행 — skill `audit-outcome` 책임 (본 BC state 를 read 만)
- 주간 process audit 수행 — skill `audit-process` 책임
- 실제 broker 매매 — G9 절대 금지
