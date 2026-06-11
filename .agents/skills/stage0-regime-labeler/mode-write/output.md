# Mode A — Narrative 작성

## 조건
helper 산출물 존재 + indicators 중 1+ 가 valid value.

## 출력
→ markdown narrative 파일 (`$TRAIL_TODAY/00-macro-regime-narrative.md`) 생성.

## 절차
1. `regime_decision` / `cash_band` / `indicators` / `regime_shift` 전체 인용 (변경 금지)
2. regime label 의미 설명
3. 각 indicator value의 사이클상 위치 설명
4. regime shift 발생 시 의미 + consecutive_days_in_current
5. cash band 의미 (보수성 vs 공격성)

## 금지
- helper numeric 변경 / 새 forecast / recommendation
