# Self-Disable Trigger — audit-outcome

## Trigger 조건

```
helper: domains.audit_integrity.stat_tests.evaluate_self_disable_trigger
조건 (강화): tier_2 - tier_1 최근 N 분기 모두 < 0  AND  Welch p_two_sided < p_max
  consecutive_required: $THRESHOLDS_PATH.statistics.self_disable_trigger.consecutive_required (default 4)
  p_max:                $THRESHOLDS_PATH.statistics.self_disable_trigger.p_max            (default 0.10)
helper 결과:
  trigger_armed = True 시 $AUDIT_DIR/disable-trigger.json 생성
  brief-author 다음 cron run 첫 줄에 trigger 표시
sign-only 충족 + p-value 미산출 (df<30) 시 'directional only' 보류 — 사용자 명시 결정 요구
```

`minimum_quarters_before_check: 4` — 누적 4분기 미만이면 check skip.

## 발동 시 부가 산출

```
$AUDIT_DIR/disable-trigger.json
{
  "triggered_at": "2026-Q4",
  "consecutive_quarters": 4,
  "quarters": ["2026-Q1", "2026-Q2", "2026-Q3", "2026-Q4"],
  "tier_diffs": [-1.6, -2.1, -0.8, -1.2],
  "user_decision_required": "LLM filter disable 또는 $THRESHOLDS_PATH / skill 재조정"
}
```

본 파일은 brief-author가 다음 cron run에서 첫 줄에 alert 출력. 사용자가
명시 결정 (`USER_DECIDED_AFTER_DISABLE_TRIGGER` 같은 ack flag) 까지 새 진입
권고 보류.
