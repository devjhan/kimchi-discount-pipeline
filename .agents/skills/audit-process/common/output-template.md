# Output Template — audit-process

경로: `$AUDIT_DIR/process-{YYYY-WW}.md`

기존 파일 존재 시 `.{N}.md` suffix 보존 (G20).

## Markdown 본문 구조

```markdown
# Process Audit — Week {YYYY-WW} ({range})

## Summary

- total cron runs in week: 5 (Mon~Fri)
- total violations: N (CRITICAL: 0, HIGH: 0, MED: 2, LOW: 4)
- verdict: PASS / FAIL_HIGH / FAIL_CRITICAL

## Violations

### CRITICAL

(none)

### HIGH

(none)

### MED

- AP-8 (date 2026-05-02): brief에 "should buy" substring 매치
  - 위치: $OPERATIONS_DIR/daily-2026-05-02/daily-brief.md:42
  - 권고: brief-author skill self-validation 강화 필요

### LOW

- AP-11 (date 2026-05-03): brief에 "1억원" 숫자가 helper citation 없이 본문 등장
  - 위치: ...

## Health Indicators

- universe 일별 변동량 평균: ±3 ticker
- d_type orphans 비율: 0%
- accepted thesis 평균: 0.4건/일 (default = no action 정상)
- needs_user_decision 평균: 0.2건/일

## Recommendations

(룰 강화 / config 임계값 조정 / skill self-validation 항목 추가 등 메타 권고만.
실제 수정은 사용자 명시 결정 후.)
```

## verdict enum

- `PASS`: violation 0 또는 LOW만
- `FAIL_MED`: MED 1+ (brief 작성 / wording 수준)
- `FAIL_HIGH`: HIGH 1+ (사이즈 / falsifier / edge_source)
- `FAIL_CRITICAL`: CRITICAL 1+ (secret leak / external raw payload — 즉시 사용자 alert)
