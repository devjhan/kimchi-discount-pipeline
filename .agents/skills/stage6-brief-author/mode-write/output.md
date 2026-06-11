# Mode A — Brief 작성

## 조건
1개 이상의 input 산출물 존재.

## 출력
→ `$DAILY_BRIEF_PATH` (= `operations/{date}/daily-brief.md`) 산출.

## 절차
1. `validate_stage_inputs($TRAIL_TODAY)` 호출 → violations 있으면 Pipeline Health에 반영
2. Input discovery → 존재하는 산출물만으로 brief 섹션 결정
3. Brief template에 따라 각 섹션 합성 — helper 숫자 인용, forbidden language redact
4. Post-write: `brief_citation_gate.sh` hook 검증 → violation 시 rewrite

## 특징
- 부분 input으로도 동작 — 누락된 stage는 omit + Pipeline Health warning
- 모든 숫자는 helper 산출물 인용 (G7) / 새 숫자 추가 금지 (G6)
- USER_PORTFOLIO_TOTAL_KRW 미입력 → 사이즈 섹션 omit (G12)
