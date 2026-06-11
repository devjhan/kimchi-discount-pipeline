# Mode A — 평가 작성

## 조건
helper 산출물 존재 + 1+ pass verdict ticker.

## 출력
→ `$TRAIL_TODAY/02-quality-lens.json` 산출.

## 절차
1. `$TRAIL_TODAY/02-quality-filter.json` read → verdict=`pass` ticker만 필터링
2. 4 lens 평가: moat, 자본배분, 회계적신호, 지주사(holding_company 한정)
3. 모든 evidence는 helper citation 또는 DART 본문 인용 (G7)
4. 미취득 데이터는 `evidence_status='partial'` + `score='insufficient_evidence'` (G8)

## 금지
- helper verdict 변경 / 정량 재계산 (G6)
- fail/unknown/caution 종목 평가 (G13)
