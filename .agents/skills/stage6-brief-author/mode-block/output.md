# Mode C — 차단 (Fatal)

## 조건
모든 input이 missing 상태거나, helper 산출물이 schema mismatch.

## 출력
→ 즉시 중단 + 사용자 명령 안내:
- Stage 0~5 pipeline run 필요 여부 보고
- 어떤 input이 누락되었는지 리스트
- `./applications/run_daily_local.sh` 또는 `./applications/daily_pipeline.sh` 실행 안내

brief 작성 시도하지 않음.
