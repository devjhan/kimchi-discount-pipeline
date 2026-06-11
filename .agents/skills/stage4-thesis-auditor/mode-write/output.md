# Mode A — 작성 가능

## 조건 (모두 충족)
- date 식별자 확정 가능 (input 또는 오늘 날짜로 default)
- `$TRAIL_TODAY/03-catalyst-events.json` 존재
- `$THRESHOLDS_PATH`의 thesis 섹션 read 가능
- accepted 후보가 1개 이상이거나, 모든 후보가 rejected / needs_user_decision로 깨끗이 분류 가능

## 출력
→ `$TRAIL_TODAY/04-thesis-candidates.json` 산출.
stdout에 1줄 요약: `[stage4-thesis] date={date} accepted=N rejected=N needs_user_decision=N -> {path}`

## 절차
1. per ticker: trigger_class 검증 (d_type 단독 → reject), quality filter 통과 확인
2. `$POSITIONS_DIR/{ticker}/thesis.md` 존재 여부로 thesis_kind 분류 (new_entry / amendment)
3. 5필드 작성: entry_catalyst → falsifier 검증 → time_horizon_months → edge_source 분류 → asymmetry_score 본문만
4. amendment 시 falsifier/edge_source/time_horizon 변경 → needs_user_decision

## 금지
- 사이즈 / Kelly / asymmetry_ratio 계산 (G6 — Stage 5 책임)
- category 외 falsifier enum / vague pattern 허용
- d_type 단독 trigger ticker를 accepted로 분류 (G15)
