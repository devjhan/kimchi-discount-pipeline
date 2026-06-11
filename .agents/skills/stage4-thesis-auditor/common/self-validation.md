# Self-Validation Checklist — stage4-thesis-auditor

산출 직전 MANDATORY 자가 검증:

```
1. AGENTS.md / $THRESHOLDS_PATH / CONTRACT/bootstrap.md 읽었는가?
2. domain/thesis-fields-format.md / falsifier-validation.md / edge-source-classification.md 읽었는가?
3. Stage 3 산출물 (03-catalyst-events.json)에서만 ticker 후보 추출했는가? (Stage 4 임의 추가 금지)
4. 모든 accepted candidate가 5필드 모두 채웠는가?
5. 모든 falsifier가 vague pattern 매치되지 않는가?
6. A claim이 있는 모든 thesis가 information_edge_evidence + confirmation_bias_check 채웠는가?
7. asymmetry_score의 ratio를 본 skill이 계산하지 않았는가? (Stage 5 책임)
8. amendment의 변경 필드가 falsifier/edge_source/time_horizon인 경우 needs_user_decision으로 escalate했는가?
9. 산출물에 forbidden language 매치 없는가?
10. 산출물에 secret env 값 노출 없는가?
11. 출력 경로가 $TRAIL_TODAY/04-thesis-candidates.json (또는 .{N}.json) 인가?
12. d_type 단독 trigger ticker가 accepted로 분류되지 않았는가?
```

NO 하나라도 있으면 산출 중단 + 누락 보고.

## 후속 권고 (자동 호출 안 함)
1. accepted 후보 → Stage 5 (sizing helper) 수동 실행 권고
2. needs_user_decision 후보 → pending_user_questions 답변 후 재실행 권고
3. 모두 rejected → 사용자 액션 없음. default = no action 정상 신호 (G11)
4. amendment 후보 → 보유 포지션 thesis 파일 변경은 사용자 결정 후 수동 trigger
