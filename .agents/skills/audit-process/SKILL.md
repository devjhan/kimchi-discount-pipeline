---
name: audit-process
description: Investment 파이프라인 주간 process audit. 지난 7일 일별 cron run의 산출물을 모두 read해 룰 위반 (vague falsifier accepted, A 단독 claim no evidence, 사이즈 cap 위반, secret leak, forbidden language 등)을 집계. $AUDIT_DIR/process-{YYYY-WW}.md 산출. 결과 outcome (수익률)은 평가하지 않는다 (별도 outcome audit). audit-report 산출 외 어떤 stage 산출물도 수정하지 않는다.
---

# audit-process — Weekly Process Audit

주간 audit. **결과(수익률)는 평가하지 않는다** — 룰을 지켰는지만 평가.
process discipline이 깨지면 outcome이 좋아도 통계적 의미 없음.

## 선행 읽기

### 공통
1. `common/violation-rules.md` — AP-1~AP-15 테이블
2. `common/output-template.md` — markdown 본문 구조 + verdict enum
3. `common/hard-guards.md` — G6/G7/G20/G21 가드
4. `common/self-validation.md` — 산출 전 체크리스트

### 분기
- `mode-write/output.md` — 정상 audit 작성 (산출물 1+ 존재)
- `mode-skip/output.md` — 산출물 부재 시 skip 조건·응답

## Required Identifier

`week: YYYY-WW (ISO week. 미지정 시 직전 ISO 주)`

## 핵심 불변식

1. **read-only audit** — 어떤 stage 산출물도 수정하지 않음
2. **severity classification** — CRITICAL(secret leak/raw payload) > HIGH(falsifier/size/edge) > MED(wording/disclaimer) > LOW(citation)
3. **secret 값 인용 금지 (G21)** — AP-9 violation 보고 시 secret 값 자체를 report 본문에 쓰지 않고 위치만 명시

## 처리 흐름

1. 7일간(또는 --range) 모든 `$TRAIL_TODAY` 산출물 + `$POSITIONS_DIR` drift 파일 scan
2. AP-1~AP-15 룰 위반 검사 (상세: `common/violation-rules.md`)
3. severity별 집계 → verdict (PASS / FAIL_MED / FAIL_HIGH / FAIL_CRITICAL / skipped)
4. `$AUDIT_DIR/process-{YYYY-WW}.md` 산출 (기존 파일 시 `.{N}.md` — G20)

## 산출물

- `$AUDIT_DIR/process-{YYYY-WW}.md`

## Out of Scope

- outcome 평가 (audit-outcome) / shadow portfolio state 갱신 (결정론 엔진) / thesis·sizing 재산출 (Stage 4/5) / config·skill 자동 수정 (사용자 명시 후)
