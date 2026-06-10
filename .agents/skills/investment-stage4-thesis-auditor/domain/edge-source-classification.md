# Edge Source Classification (Stage 4)

본 문서는 thesis의 `edge_source` 필드 분류 절차다. AGENTS.md "엣지 원천
명시" 원리 + $THRESHOLDS_PATH.thesis.edge_source가 single source. 본
문서는 분류 enum과 A claim에 대한 추가 검증 절차를 정의한다.

---

## 1. 4 Categories

| code | 이름 | 의미 | retail에 valid한가 |
|---|---|---|---|
| `A` | 정보 edge | 시장보다 더 잘 안다 | 거의 false. 인용 시 추가 검증 강제 |
| `B` | 행동 edge | 시장이 편향에 빠짐 (recency, narrative, panic, herding) | valid (forced selling / panic earnings 등) |
| `C` | 구조 edge | institutional이 진입 못 한다 (사이즈 / IPS / 유동성 / 한국어 / 회계 특수성) | retail의 본질적 edge |
| `D` | 시간 edge | horizon이 길어 분기 P&L 압박 없음 | retail의 본질적 edge |

각 thesis는 `primary` array에 1+ 명시. `["C", "D"]`가 본 시스템의 default
"edge stack" — 두 카테고리를 같이 인용해야 high-conviction.

---

## 2. A claim 추가 검증 (information edge warning)

`primary`에 `"A"`가 포함되면 `information_edge_claimed=true` 자동 set + 다음
검증 강제:

### 2.1 필수 evidence

`information_edge_evidence` 필드에 다음 중 1+ helper citation:

```
- DART 공시의 정량 신호 + 일반 사용자가 같은 공시에서 도달 못 하는 추론
- 정량 데이터 (KIS, FRED, Yahoo) 의 비대칭 해석
- 사용자 본인의 industry insider 경험 (이 경우 외부 검증 불가, fallback to B/C/D)
```

evidence가 없거나 generic ("내 분석", "내 직관") 이면 reject.

### 2.2 confirmation bias check

LLM이 다음 질문 본문에 명시 답변:

```
Q1. 이 정보 edge가 시장 가격에 이미 반영되었을 가능성은?
Q2. 시장이 같은 정보를 보고 다른 결론에 도달한 이유는?
Q3. 이 edge가 false면 어느 falsifier가 trigger되는가?
```

답변 본문이 "시장이 틀렸다", "내가 맞다" 류 단정만 있고 정량/구조 추론
없으면 reject. 본 검증은 claim에 대한 외부 reference를 강제한다.

### 2.3 fallback 권고

A claim이 fail하면, LLM은 다음 fallback 시도:

```
"이 thesis가 사실 A가 아닌 B(행동) / C(구조) / D(시간) edge로 분류 가능한가?"
```

가능하면 `primary`에서 `"A"` 제거 후 재검증. 불가능하면 reject + 사용자에게
edge_source 재작성 권고.

---

## 3. require_c_or_d_for_high_conviction

`$THRESHOLDS_PATH.thesis.edge_source.require_c_or_d_for_high_conviction: true`
이면 다음 추가 검증:

- thesis가 단일 종목 5% 이상 (sizing 권장 > 5%) 받으려면 `primary`에 `C` 또는
  `D` 중 1+ 필수. 없으면 verdict=`accepted`라도 Stage 5에서 size 절반 cap
- 본 검증은 `metadata.high_conviction_eligibility` 필드로 명시:
  ```json
  "high_conviction_eligibility": {
    "eligible": false,
    "reason": "primary edge_source has no C or D"
  }
  ```

Stage 4가 cap을 직접 적용하지는 않음 (G6 — sizing은 Stage 5). 본 필드는
Stage 5 helper가 input으로 사용.

---

## 4. Anti-Pattern Detection

다음 rationale 패턴은 edge_source 분류에 무관하게 추가 LLM 검증:

| pattern | 검증 |
|---|---|
| `"undervalued"` 단독 | bootstrap.md Section 3 forbidden valuation. reference / DCF / NAV citation 강제 |
| `"long-term winner"` | falsifier 본문에 명시적 exit 조건 없으면 reject (G5) |
| `"기관이 모른다"` (C-claim의 vague version) | 어느 institutional 제약 (size / IPS / mandate / 유동성) 인지 명시 강제 |
| `"horizon이 다르다"` (D-claim의 vague version) | 분기 P&L 압박이 어떤 mechanism으로 mispricing 만드는지 명시 강제 |

---

## 5. Examples

### 5.1 ALLOW — C + D combo

```json
{
  "primary": ["C", "D"],
  "rationale": "OO지주는 시총 4000억으로 외국계/대형 펀드 entry 어려움 (mandate 최소 5000억). 자사주 소각 누적 5%p로 NAV 할인 좁힘 catalyst, 좁힘까지 12~24개월 소요 추정 — 분기 P&L 압박 없는 retail horizon이 hold 가능 (C+D).",
  "information_edge_claimed": false,
  "information_edge_evidence": null
}
```

### 5.2 ALLOW — B (forced selling)

```json
{
  "primary": ["B"],
  "rationale": "MSCI Korea Small Cap 편출 통보 (2026-04-15) → index 추종 펀드 강제 매도. thesis intact 가정 시 panic discount는 60일 내 회복 사례 존재 (사용자 보유 backtest log 인용 — N=12, 평균 회복기간 47일).",
  "information_edge_claimed": false,
  "information_edge_evidence": null
}
```

### 5.3 ALLOW — A with strong evidence

```json
{
  "primary": ["A", "C"],
  "rationale": "DART@2026-04-30 별도재무제표에서 자회사 OO에 대한 영업 양수도 결정 공시 — 회사 본문은 generic이나, 같은 공시 첨부 별표의 자회사 매출 개시일이 본사 영업 양도 시점과 4개월 차이로 명시됨. 일반 사용자가 첨부 별표까지 read 가능하나 attention 부족 추정. 동시에 시총 600억으로 institutional entry 어려움 (C).",
  "information_edge_claimed": true,
  "information_edge_evidence": "DART@2026-04-30={rcept_no:20260430000456,attached_table:appendix_3.xlsx}",
  "confirmation_bias_check": {
    "q1": "공시 직후 1주일 거래량 평균 대비 +18% — 일부 시장 참여자는 인지함. 그러나 attention 비율은 여전히 낮음 (Naver 종목 게시판 mention < 10건/일).",
    "q2": "시장은 본문 generic 텍스트만 보고 routine 영업 재편으로 해석 — 첨부 별표의 timing 불일치를 catch한 분석은 보이지 않음.",
    "q3": "12개월 내 자회사 OO 매출 quarterly disclosure에서 본사 영업 양도분이 일치 안 하면 thesis fail (metric_trigger falsifier)"
  }
}
```

### 5.4 DENY — A 단독 + generic rationale

```json
{
  "primary": ["A"],
  "rationale": "내 산업 분석으로 봤을 때 이 회사가 향후 좋아질 것이라 본다.",
  "information_edge_claimed": true,
  "information_edge_evidence": null
}
```

→ reject, rejection_reason: `"A claim with no helper citation; rationale is generic 'looks good' statement (edge-source-classification.md Section 2.1)"`

### 5.5 DENY — C-claim vague

```json
{
  "primary": ["C"],
  "rationale": "기관이 모르는 종목이다."
}
```

→ reject, rejection_reason: `"C-claim vague: institutional constraint not specified (size / IPS / mandate / liquidity / Korean accounting). See edge-source-classification.md Section 4."`

---

## 6. LLM 검증 Procedure

```
1. primary array가 enum {A, B, C, D} 중 1+ 인지 확인.
2. "A" 포함 시 information_edge_claimed=true 강제 + 2.1, 2.2 검사.
3. C-claim / D-claim에 vague pattern 매치 시 rationale 재작성 강제.
4. require_c_or_d_for_high_conviction=true 시 high_conviction_eligibility 필드 산출.
5. 모든 검증 pass 시 verdict=accepted 후보로 (다른 4개 필드도 통과한 경우만).
```
