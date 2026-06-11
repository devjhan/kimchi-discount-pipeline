# Self-Validation — audit-outcome

산출 전 MANDATORY 체크리스트:

1. shadow-portfolio-state.json read-only로 처리했는가?
2. sample_gate에 따른 wording 룰 정확히 적용했는가?
3. self-disable trigger consecutive count 정확히 4인지 검증했는가?
4. 본문에 forbidden statistical wording 매치 없는가?
5. 출력 경로가 `$AUDIT_DIR/outcome-{YYYY-Q}.md` (또는 `.{N}.md`) 인가?

NO 하나라도 있으면 중단 + 보고.
