# Thesis Fields Format (Stage 4)

본 문서는 Stage 4 thesis-auditor가 입력으로 받고 산출하는 thesis의 5필드
구조와 JSON schema를 정의한다. 본 문서가 $THRESHOLDS_PATH.thesis 섹션과
충돌하면 $THRESHOLDS_PATH이 우선 (CONTRACT/bootstrap.md Section 1).

---

## 1. 5 Required Fields

모든 thesis (신규 + amendment)는 다음 5필드 모두 포함. 누락 시 verdict=`rejected`.

| 필드 | 타입 | 의미 | reject 조건 |
|---|---|---|---|
| `entry_catalyst` | string | trigger event 인용 (Stage 3 catalyst event id 또는 외부 ingest signal id 명시) | Stage 3 산출물에 매칭 event 없음 / id 누락 |
| `falsifier` | object | 손절 / exit 조건. `falsifier-validation.md` 참조 | category 누락, vague pattern 매치, max_months 초과 |
| `time_horizon_months` | integer | 진입 후 보유 기대 개월 수 | $THRESHOLDS_PATH.thesis.time_horizon_months 범위 (default 6~60) 외 |
| `edge_source` | array<string> | A/B/C/D 중 1+ . `edge-source-classification.md` 참조 | enum 외 값 / A 단독 인용 시 추가 검증 fail |
| `asymmetry_score` | object | downside_floor / upside_ceiling. `compute` 영역 = Stage 5 책임 | downside_floor / upside_ceiling citation 누락, ratio 산출 시도 (Stage 4 외 책임) |

### 1.1 `entry_catalyst` 형식

```json
{
  "catalyst_id": "DART-20260415-00046127",
  "catalyst_type": "treasury_share_cancellation",
  "stage3_reference": "$OPERATIONS_DIR/daily-2026-04-30/03-catalyst-events.json#catalysts[3]",
  "trigger_class": "a_type"
}
```

`trigger_class` ∈ `{a_type, b_type}`. `d_type` 단독 진입 금지 (handoff doc G15 / $THRESHOLDS_PATH.catalyst.trigger_rule.augment_only).

### 1.2 `falsifier` 형식

`falsifier-validation.md` 본문 참조. 최소 1 카테고리, 복수 가능.

```json
{
  "categories": ["time_cap", "metric_trigger"],
  "items": [
    {
      "category": "time_cap",
      "statement": "24개월 내 NAV 할인 좁힘 catalyst 0건이면 exit",
      "max_months": 24
    },
    {
      "category": "metric_trigger",
      "statement": "ROIC TTM이 6% 이하로 떨어지면 exit",
      "metric": "ROIC_TTM",
      "threshold": 0.06,
      "direction": "below"
    }
  ]
}
```

### 1.3 `edge_source` 형식

```json
{
  "primary": ["C", "D"],
  "rationale": "institutional이 size / IPS로 진입 불가 (C); 분기 P&L 압박 없는 retail horizon (D)",
  "information_edge_claimed": false,
  "information_edge_evidence": null
}
```

`primary`에 `"A"` 포함 시 `information_edge_claimed=true`로 강제 + `information_edge_evidence`에 helper citation 필수. 누락 시 reject.

### 1.4 `asymmetry_score` 형식

Stage 4는 **숫자 산출 안 한다** (G6 — Stage 5 책임). thesis 작성자는 다음만 작성:

```json
{
  "downside_floor": {
    "krw_per_share_or_pct": "-30%",
    "rationale": "NAV 할인 80%까지 확대 시 추가 -30%, 이후 floor",
    "source_citation": "DART@2026-04-30={NAV_per_share:KRW_152000}"
  },
  "upside_ceiling": {
    "krw_per_share_or_pct": "+120%",
    "rationale": "NAV 할인 평균(50%) 회귀 + 자사주 소각 누적 5%p",
    "source_citation": "DART@2026-04-30={NAV_per_share:KRW_152000}"
  },
  "computed_ratio": null,
  "computed_by": "stage5_helper_pending"
}
```

`computed_ratio`는 Stage 5 sizing helper가 채운다. Stage 4가 ratio 직접 계산 시 G6 위반.

---

## 2. Verdict Enum

Output entry의 `verdict` 필드는 다음 중 하나:

| verdict | 의미 | follow-up |
|---|---|---|
| `accepted` | 5필드 모두 valid + falsifier non-vague + edge_source non-A or A+evidence | Stage 5 sizing 진행 |
| `rejected` | 필드 누락 / vague falsifier / time_horizon out-of-range / d_type 단독 trigger / 기타 hard guard 위반 | rejection_reason 필드에 사유 명시, Stage 5로 전달 안 함 |
| `needs_user_decision` | helper citation 부재 / Stage 3 reference resolve 실패 / 정량 추정 모호 / amendment 변경량 큼 | thesis 본문에 `pending_user_questions` 필드로 묶음 질문 출력 |

`accepted` 외엔 사이즈 산출 진입 금지. `needs_user_decision`은 사용자가 답할 때까지 다음 cron run에서 동일 catalyst로 재진입 시도하지 않음 (state는 `04-thesis-candidates.json` 본문에 보존).

---

## 3. Output JSON Schema

```json
{
  "schema": "investment-stage4-thesis-candidates-v1",
  "generated_at": "2026-05-04T17:30:00+09:00",
  "date": "2026-05-04",
  "stage3_input": "$OPERATIONS_DIR/daily-2026-05-04/03-catalyst-events.json",
  "stats": {
    "total_candidates_scanned": 7,
    "accepted": 1,
    "rejected": 4,
    "needs_user_decision": 2
  },
  "candidates": [
    {
      "ticker": "KR:003550",
      "name": "LG",
      "thesis_kind": "new_entry",
      "verdict": "accepted",
      "thesis": {
        "entry_catalyst": { },
        "falsifier": { },
        "time_horizon_months": 24,
        "edge_source": { },
        "asymmetry_score": { }
      },
      "rejection_reason": null,
      "pending_user_questions": [],
      "amendment_diff": null
    },
    {
      "ticker": "KR:000810",
      "name": "삼성화재우",
      "thesis_kind": "amendment",
      "verdict": "needs_user_decision",
      "thesis": { },
      "rejection_reason": null,
      "pending_user_questions": [
        "기존 thesis의 falsifier(`time_cap=18개월`)를 24개월로 연장 — 추가 catalyst 발동(자사주 소각)이 카운트 reset인지 사용자 결정 필요"
      ],
      "amendment_diff": {
        "previous_path": "$POSITIONS_DIR/KR-000810/thesis.md",
        "fields_changed": ["falsifier", "time_horizon_months"]
      }
    }
  ],
  "warnings": []
}
```

### 3.1 Path Convention

산출물은 CONTRACT/bootstrap.md Section 2 표 따른다:

```
$TRAIL_TODAY/04-thesis-candidates.json
```

기존 파일 존재 시 `.{N}.json` suffix로 보존 (덮어쓰기 금지).

### 3.2 Amendment 처리

기존 보유 포지션의 thesis 파일 (`$POSITIONS_DIR/{ticker}/thesis.md`)이 존재하면:

- 동일 ticker가 Stage 3 trigger에서 다시 등장 → amendment 후보
- `thesis_kind = "amendment"` 부여
- `amendment_diff.fields_changed` 에 변경 필드 list 명시
- 기존 thesis와 falsifier가 다르면 자동 reject 대신 `needs_user_decision`으로 escalate
  (보유 포지션 thesis 임의 수정 금지 — handoff doc Section 7 + bootstrap.md Section 7)

---

## 4. Stage 4가 절대 산출하지 않는 것

- 가격 / 사이즈 / Kelly fraction / portfolio weight (Stage 5 책임 — G6)
- 매매 timing / 진입 시점 / 분할매수 plan (Stage 5 + 사용자 책임)
- "should buy / sell" 류 wording (G3 — bootstrap.md Section 3 forbidden)
- 기존 포지션 thesis 본문 자동 수정 (`needs_user_decision`으로 escalate)
- Stage 3에 없는 catalyst를 새로 발견해 thesis 진입 (G14 — Stage 4 universe expansion 금지)
