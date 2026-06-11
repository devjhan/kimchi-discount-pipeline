# Self-Validation — Stage 6 Brief Author

brief 작성 완료 후 다음 7-step checklist로 자가 검증을 수행한다.

---

## Self-Validation Checklist

```
1. 모든 본문 숫자가 helper 산출물 인용 (source_citation) 인가?
   → 형식: {source}@{ISO_timestamp}={value}
   → helper 산출물 외 숫자 존재 시 즉시 redact 또는 'n/a' 대체

2. forbidden language (recommendation / statistical / valuation) substring 매치 없는가?
   → bootstrap.md Section 3 + $THRESHOLDS_PATH.enforcement.forbidden_language
   → 매치 시 evidence-based phrasing으로 대체

3. USER_PORTFOLIO_TOTAL_KRW 미입력 시 사이즈 섹션 omit했는가?
   → Sizing Recommendation 섹션 전체 omit 확인

4. helper missing 섹션은 본문에 'omitted (reason: ...)' 명시했는가?
   → Pipeline Health 섹션의 skipped sources list와 일치 확인

5. external-signals raw payload 노출 안 했는가?
   → $EXTERNAL_SIGNALS_DIR/ 산출물만 인용, raw content 노출 금지

6. secret env 노출 없는가?
   → DART_API_KEY / KIS_APP_SECRET / KIS_ACCOUNT_NUMBER / TELEGRAM_BOT_TOKEN
     등이 brief 본문 / stdout에 등장하지 않는지 확인

7. 출력 경로가 $DAILY_BRIEF_PATH (= $TRAIL_TODAY/../daily-brief.md) (또는 .{N}.md) 인가?
   → operations/{date}/daily-brief.md 경로 확인
   → 기존 파일 존재 시 .{N}.md suffix 적용 확인
```

---

## Out of Scope

Stage 6 brief author가 **절대 수행하지 않는** 작업:

- 새 thesis 작성 (Stage 4 영역)
- 사이즈 재계산 (Stage 5 영역)
- regime classification 변경 (Stage 0 helper 영역)
- universe 추가 (Stage 1 helper 영역)
- 외부 신호 ingest (`/ingest-external-signal` 별도 skill)
- Telegram / 이메일 push (별도 `infrastructure/notify/dispatcher` 영역)
- Stage 0~5 helper script의 산출물 수정
- 보유 포지션 thesis 임의 수정
