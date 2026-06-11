# Self-Validation — stage2-quality-lens

산출 전 MANDATORY 체크리스트:

1. helper 산출물에서 verdict=`pass` 종목만 평가 대상으로 했는가?
2. ROIC / debt / FCF 숫자를 본 skill에서 재계산하지 않았는가?
3. 모든 정성 score에 evidence citation 또는 `evidence_status` marker 있는가?
4. 지주사 lens는 `source_category=holding_company` 종목에만 적용했는가?
5. forbidden wording 없는가?
6. helper verdict=`fail` / `unknown` / `caution` 종목을 평가하지 않았는가? (오직 `pass` 만)

NO 하나라도 있으면 중단 + 보고.
