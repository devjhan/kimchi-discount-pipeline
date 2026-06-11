---
name: stage2-quality-lens
description: Investment 파이프라인 Stage 2의 LLM 정성 lens 평가 단계. screener 패키지 (domains.screener.main)의 deterministic 통과(verdict='pass') 종목에 대해서만 4 lens (moat / 자본배분 / 회계 적신호 / 지주사 자회사 매력도)를 평가. helper의 numeric verdict는 변경하지 않고 lens 보조 의견만 추가. $TRAIL_TODAY/02-quality-lens.json 산출. ROIC/debt/FCF 등 정량 재계산 일체 금지 (helper 책임).

---

# stage2-quality-lens — Quality Qualitative Lens Evaluator

Stage 2 hybrid LLM 단계. helper의 deterministic verdict가 `pass`인 종목에 대해서만 4개 정성 lens를 평가한다. helper가 `fail`/`unknown`/`caution`으로 분류한 종목은 평가하지 않는다.

## 선행 읽기

### 공통
1. `common/lenses.md` — 4 lens 기준 상세
2. `common/output-schema.md` — JSON schema
3. `common/hard-guards.md` — guard table
4. `common/self-validation.md` — 체크리스트

### 분기
- `mode-write/output.md` — 정상 평가 작성 조건·절차
- `mode-no-pass/output.md` — pass 종목 0건 시 빈 산출물 조건
- `mode-block/output.md` — helper 산출물 누락 시 차단 조건·응답

## 핵심 불변식

1. **helper verdict 불변** — `fail`/`unknown`/`caution` 종목을 `pass`로 임의 변경 금지 (G13)
2. **정량 재계산 금지 (G6)** — ROIC/debt/FCF 등 helper metric을 본 skill에서 재계산하지 않음
3. **fail 종목 평가 금지** — 오직 helper verdict=`pass` 종목만 lens 평가 대상

## 산출물

- `$TRAIL_TODAY/02-quality-lens.json`

## Out of Scope

- helper metric 재계산/verdict 변경 / catalyst 평가 (Stage 3) / thesis 작성 (Stage 4) / 사이즈·Kelly 계산 (Stage 5)
