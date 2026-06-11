# Self-Validation — audit-process

산출 전 MANDATORY 체크리스트:

1. 일별 산출물 read-only로 처리 (수정 0)했는가?
2. AP-9 violation 본문에 secret 값 자체 인용하지 않았는가?
3. verdict가 4 enum 중 1개로 명확한가?
4. recommendations는 메타 (config / skill 강화) 수준이고, 사용자 자본 운용 권고는 없는가?
5. 출력 경로가 `$AUDIT_DIR/process-{YYYY-WW}.md` (또는 `.{N}.md`)인가?

NO 하나라도 있으면 중단 + 보고.
