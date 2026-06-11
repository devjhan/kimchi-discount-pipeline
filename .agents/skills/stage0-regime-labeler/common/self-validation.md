# Self-Validation — stage0-regime-labeler

산출 전 MANDATORY 체크리스트:

1. helper 산출물 (`00-macro-regime.json`) 의 `regime_decision.regime` / `cash_band` / `indicators` 그대로 인용 했는가?
2. helper가 산출하지 않은 숫자가 본문에 나오지 않는가?
3. forbidden wording 매치 없는가? (`domain/forbidden-language.md` 참조)
4. recommendation / 매매 권고 본문에 없는가?
5. secret env 노출 없는가?
6. 출력 경로가 `$TRAIL_TODAY/00-macro-regime-narrative.md` 또는 `.{N}.md` 인가?

NO 하나라도 있으면 중단 + 보고.
