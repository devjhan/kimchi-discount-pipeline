# 반증 가능성 (Falsifiability — Popper for Thesis)

## 원리

Karl Popper의 과학철학: 어떤 진술이 과학적이려면 **그것을 거짓으로 만들 수
있는 구체적 조건**이 있어야 한다. 반증 trigger 없는 thesis는 narrative
다. "이 종목 좋다", "장기적으로 오를 것" 류의 진술은 어떤 결과로도
반박되지 않으므로 thesis가 아니다.

본 시스템은 모든 진입 thesis에 구체적 falsifier를 강제. 사용자가 falsifier
조건이 발동했을 때 어떻게 행동할지 (사이즈 절반 / 청산 / 재평가) 가
명확하지 않으면 시스템 차원에서 thesis 작성 단계 reject.

---

## 본 시스템에서의 의미

모든 thesis는 다음 3 카테고리 중 1+ falsifier 명시:

| 카테고리 | 형식 | 예시 |
|---|---|---|
| `time_cap` | "X개월 내 catalyst Y 발생 안 하면 exit" | "24개월 내 NAV 할인 좁힘 catalyst 0건이면 exit" |
| `metric_trigger` | "metric Z가 W 이하/이상 도달 시 exit" | "ROIC TTM이 6% 이하 도달 시 exit" |
| `event_trigger` | "event V 발생 시 exit" | "행동주의 펀드 5% 신고 철회 또는 청산 공시 시 exit" |

---

## Enforcement

| Layer | 내용 |
|---|---|
| `thresholds.yaml.thesis` | required_fields=falsifier 강제, falsifier_categories 정의, falsifier_vague_patterns_reject 자동 reject |
| `~/.agents/skills/stage4-thesis-auditor/domain/falsifier-validation.md` | vague pattern 사전 검사 + 카테고리별 필수 필드 + anti-pattern (fake specificity 검출) |
| `scripts/stage5-sizing.py` | (future) falsifier proximity monitoring helper와 join — proximity high 시 사이즈 절반 alert |
| `~/.agents/skills/audit-process/SKILL.md` | 주간 audit에서 falsifier vague 사례 / proximity tracking 누락 사례 flag |

---

## Vague Pattern (자동 reject)

`thresholds.yaml.thesis.falsifier_vague_patterns_reject` + 추가:

- "실적 안 좋으면", "thesis 깨지면", "전망 나빠지면", "기대대로 안 가면"
- "if it doesn't work out", "if things change"
- "상황이 바뀌면", "분위기가 바뀌면"
- "어쩐지", "왠지" (정량성 부재)

---

## Anti-Pattern: Fake Specificity

형식상 5필드를 채웠지만 실제로는 vague:

| pattern | 사유 |
|---|---|
| `metric=stock_price`, `threshold=0`, `direction=below` | tautological |
| `event_pattern=any major news`, `monitoring_source=manual` | "anything bad" 우회 |
| `max_months=60`, `expected_catalyst=management decision` | horizon 최대 + catalyst 비측정 |

위 패턴은 reject 대신 `needs_user_decision`으로 escalate (사용자 재작성 권고).

---

## Daily Monitoring (Falsifier Proximity)

보유 포지션의 falsifier proximity는 일별 cron에서 자동 검사:

```
proximity = low | medium | high
```

산출 위치: `.handoff/positions/{ticker}/drift-{date}.md`. trigger 임박 시
push notification (Telegram / scheduled-tasks MCP).

자동 청산은 절대 금지 (G9). agent는 alert만, 청산 실행은 사용자.

---

## Allowed Patterns

```
- 같은 thesis에 time_cap + metric_trigger 복수 falsifier OK
- max_months ≤ macro_config.thesis.falsifier_categories.time_cap.max_months (default 36)
- metric은 helper script로 측정 가능해야 함 (측정 helper 미구현 시 needs_user_decision)
- 행동주의 fund의 5% 보유 철회 = event_trigger의 valid event_pattern (DART 측정 가능)
- amendment의 falsifier 수정은 사용자 결정 필수 (보유 포지션 thesis 임의 수정 금지)
```

---

## Cross-references

- 본 문서는 AGENTS.md "2. 반증 가능성" 의 enforcement 상세
- bootstrap.md Section 4 (Required Fields per Thesis) + thresholds.yaml.thesis single source
- 충돌 시: thresholds.yaml > 본 문서 > skill 본문
