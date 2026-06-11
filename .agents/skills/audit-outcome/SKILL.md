---
name: audit-outcome
description: Investment 파이프라인 분기 outcome audit. 4-tier shadow portfolio (Index / Mechanical / LLM-Filtered / Random) 의 분기 누적 수익률을 비교해 LLM filter (tier_2)의 부가가치를 검증한다. tier_2 < tier_1 4분기 연속 시 self-disable trigger 발동. $AUDIT_DIR/outcome-{YYYY-Q}.md 산출. shadow portfolio state 자체는 domains.audit_integrity.main 결정론 엔진이 일별 갱신하며, 본 skill은 read-only 비교만 수행.
---

# audit-outcome — Quarterly Outcome Audit

4-tier shadow portfolio counterfactual 비교로 LLM filter의 부가가치를 통계적으로 측정.
4분기 연속 tier_2가 tier_1보다 열위면 self-disable trigger 발동. state 갱신은
`domains.audit_integrity.main` 결정론 엔진 책임, 본 skill은 read-only 비교만 수행.

## 선행 읽기

### 공통
1. `common/computation.md` — 분기 수익률 계산 + stat_tests 호출
2. `common/output-template.md` — markdown 본문 구조 + verdict enum
3. `common/self-disable-trigger.md` — self-disable trigger 조건·발동
4. `common/hard-guards.md` — G6/G19/G20 가드
5. `common/self-validation.md` — 산출 전 체크리스트

### 분기
- `mode-write/output.md` — 정상 audit 작성 조건·절차
- `mode-insufficient/output.md` — 운영 1분기 미만 보류 조건
- `mode-block/output.md` — state 부재 차단 조건·응답

## Required Identifier

`quarter: YYYY-Q (예: 2026-Q2). 미지정 시 직전 quarter`

## 핵심 불변식

1. **read-only 비교** — state 갱신은 결정론 엔진 책임, 본 skill은 읽기 전용
2. **sample size gate (G19)** — N<30: 부호만 / 30≤N<100: p<0.10 / N≥100: p<0.05
3. **self-disable trigger 4분기** — tier_2 < tier_1 4분기 연속 + Welch p < p_max → trigger

## 처리 흐름

1. `$AUDIT_DIR/shadow-portfolio-state.json` read → 분기 판단 (Mode A/B/C)
2. Mode A: 각 tier 분기 수익률 계산, tier 비교, sample_gate 적용, self-disable check
3. 통계 계산은 모두 `domains.audit_integrity.stat_tests` helper 인용 (G6)

## 산출물

- `$AUDIT_DIR/outcome-{YYYY-Q}.md`
- trigger 발동 시 `$AUDIT_DIR/disable-trigger.json` 추가

## Out of Scope

- state 갱신 (결정론 엔진) / process audit (audit-process) / 자동 LLM filter disable (사용자 명시 결정 후)
