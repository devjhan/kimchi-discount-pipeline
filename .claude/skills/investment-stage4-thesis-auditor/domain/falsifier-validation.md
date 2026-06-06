# Falsifier Validation (Stage 4)

본 문서는 thesis의 `falsifier` 필드 검증 절차다. CONTRACT/bootstrap.md
Section 4 + $THRESHOLDS_PATH.thesis 가 single source. 본 문서는 절차와
edge case를 설명한다.

---

## 1. 3 Categories (반드시 1+ 포함)

`$THRESHOLDS_PATH.thesis.falsifier_categories`:

### 1.1 `time_cap`

```
"X개월 내 catalyst Y 발생 안 하면 exit"
```

- 필수 필드: `max_months` (integer, 1 ≤ X ≤ $THRESHOLDS_PATH.thesis.falsifier_categories.time_cap.max_months, default 36)
- 필수 필드: `expected_catalyst` (X 동안 발동 기대하는 구체 event 명)
- statement 본문에 `expected_catalyst`가 포함되지 않으면 reject

### 1.2 `metric_trigger`

```
"metric Z가 W 이하/이상 도달 시 exit"
```

- 필수 필드: `metric` (string, 예: `ROIC_TTM`, `NAV_discount_pct`, `debt_to_equity`)
- 필수 필드: `threshold` (number)
- 필수 필드: `direction` ∈ `{above, below, equal}`
- metric은 helper script로 측정 가능해야 함 — 측정 helper 미구현이면 `needs_user_decision`

### 1.3 `event_trigger`

```
"event V 발생 시 exit"
```

- 필수 필드: `event_pattern` (string, DART 공시 type 또는 외부 event 명)
- 필수 필드: `monitoring_source` ∈ `{DART, KIS, FRED, Yahoo, manual}`

---

## 2. Vague Pattern Detection (자동 reject)

다음 패턴이 statement 본문에 substring 매치되면 reject. 매치는 case-insensitive,
한국어/영문 양방향.

### 2.1 $THRESHOLDS_PATH.thesis.falsifier_vague_patterns_reject

```
- "실적 안 좋으면"
- "thesis 깨지면"
- "전망 나빠지면"
- "기대대로 안 가면"
- "if it doesn't work out"
```

### 2.2 추가 vague pattern (CONTRACT/bootstrap.md Section 4)

```
- "if things change"
- "상황이 바뀌면"
- "분위기가 바뀌면"
- "기조가 변하면"
- "...될 것 같으면"     (구체 event/metric 미명시)
- "어쩐지", "왠지"        (정량성 부재)
```

### 2.3 구조적 vague signal (정규식 기반)

| signal | reject 사유 |
|---|---|
| `category=time_cap` 인데 `max_months` 누락 | time-cap의 시간 요소 미명시 |
| `category=metric_trigger` 인데 `threshold` 또는 `direction` 누락 | metric의 정량 요소 부재 |
| `category=event_trigger` 인데 `event_pattern`이 generic ("nego", "bad news", "이슈 발생") | 구체 event 미식별 |
| 모든 카테고리에 statement 본문 길이 < 15자 | 정보량 부재 (heuristic) |

---

## 3. Validation 절차 (LLM이 수행)

```
1. falsifier가 array<object>인지 확인. items 비어있으면 reject.
2. 각 item의 category 필드가 enum {time_cap, metric_trigger, event_trigger}인지 확인.
3. statement 본문에 vague pattern substring 매치 검사 (Section 2.1, 2.2).
   매치 → reject, rejection_reason에 매치된 pattern 명시.
4. 카테고리별 필수 필드 검사 (Section 1).
5. time_cap의 max_months가 $THRESHOLDS_PATH.thesis.falsifier_categories.time_cap.max_months 초과 시 reject.
6. metric_trigger의 metric이 helper로 측정 가능한지 확인.
   측정 helper 미구현 → needs_user_decision (reject 아님 — falsifier 자체는 valid).
7. event_trigger의 monitoring_source가 enum {DART, KIS, FRED, Yahoo, manual}인지 확인.
```

---

## 4. Examples

### 4.1 ALLOW — time_cap

```json
{
  "category": "time_cap",
  "statement": "24개월 내 NAV 할인 좁힘 catalyst (자사주 소각 / 인적분할 / 합병) 0건이면 exit",
  "max_months": 24,
  "expected_catalyst": "treasury_share_cancellation OR spin_off OR merger"
}
```

### 4.2 ALLOW — metric_trigger

```json
{
  "category": "metric_trigger",
  "statement": "EPS guidance가 직전 분기 대비 -10% 이상 하향 시 exit",
  "metric": "EPS_guidance_QoQ",
  "threshold": -0.10,
  "direction": "below"
}
```

### 4.3 ALLOW — event_trigger

```json
{
  "category": "event_trigger",
  "statement": "행동주의 펀드 5% 신고 철회 또는 청산 공시 시 exit",
  "event_pattern": "DART_5pct_filing_withdrawal OR liquidation_disclosure",
  "monitoring_source": "DART"
}
```

### 4.4 DENY — vague pattern

```json
{
  "category": "time_cap",
  "statement": "thesis 깨지면 exit",
  "max_months": 12
}
```

→ reject, rejection_reason: `"vague pattern matched: 'thesis 깨지면' ($THRESHOLDS_PATH.thesis.falsifier_vague_patterns_reject)"`

### 4.5 DENY — missing required field

```json
{
  "category": "metric_trigger",
  "statement": "ROIC가 떨어지면 exit"
}
```

→ reject, rejection_reason: `"metric_trigger missing required fields: metric, threshold, direction"`

---

## 5. Composition Rules

복수 falsifier item 허용. 단:

- 같은 category 내 동일 metric / 동일 event_pattern 중복 금지 (사용자 의도 모호)
- time_cap은 하나만 (여러 time_cap이 있으면 가장 짧은 것만 유효 — Stage 5 monitoring loop 단순화)
- Stage 4는 falsifier 정합성만 검증, "어떤 falsifier가 실제 trigger 가능성이 높은가"는 평가 안 함 (정량 평가는 Stage 5 / 후속 monitoring 책임)

---

## 6. Anti-Pattern: Fake Specificity

다음은 형식상 5필드를 채웠지만 실제로는 vague — LLM이 추가 검사 강제:

| pattern | 사유 |
|---|---|
| `metric=stock_price`, `threshold=0`, `direction=below` | tautological (가격 0 도달 = absorbing barrier, falsifier로 의미 없음) |
| `event_pattern=any major news`, `monitoring_source=manual` | "anything bad" 우회 |
| `max_months=60`, `expected_catalyst=management decision` | horizon이 $THRESHOLDS_PATH.thesis.time_horizon_months.max에 닿고 catalyst가 정량 측정 불가능 |

위 패턴 발견 시 reject 대신 `needs_user_decision`으로 escalate + `pending_user_questions`에 구체 사유 명시.
