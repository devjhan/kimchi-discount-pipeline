# 엣지 원천 명시 (Edge Source Articulation)

## 원리

"왜 시장이 틀렸는가" 라는 inverse question에 답하지 못하면 thesis 아님.
investment의 모든 alpha는 시장의 비효율에서 발생한다 — 시장 참여자가
어떤 구조적 제약 / 행동적 편향 / 정보 격차 / 시간 horizon 차이 때문에 이
가격에 도달했는지 명시 못 하면, 그 진입은 statistical noise를 alpha로
오해할 가능성이 높다.

본 시스템은 모든 thesis에 4 분류 (A/B/C/D) 중 1+ 명시 강제. retail의
본질적 edge는 **C (구조) + D (시간)** 의 결합이며, A (정보 edge) 는 거의
false — institutional 대비 정보 격차에서 retail이 우위에 설 가능성은
구조적으로 작다.

---

## 4 분류

| 코드 | 이름 | 의미 | retail valid 여부 |
|---|---|---|---|
| **A** | 정보 edge | 시장보다 더 잘 안다 | 거의 false. 인용 시 추가 검증 강제 |
| **B** | 행동 edge | 시장이 편향에 빠짐 (recency, narrative, panic, herding) | valid (forced selling / panic earnings) |
| **C** | 구조 edge | institutional이 진입 못 한다 (사이즈 / IPS / 유동성 / 한국어 / 회계 특수성) | retail의 본질적 edge |
| **D** | 시간 edge | horizon이 길어 분기 P&L 압박 없음 | retail의 본질적 edge |

---

## 본 시스템에서의 의미

핵심 비대칭:

```
Institutional의 강제 (mandate / size / 분기 P&L) → 가격 inefficiency
                              ↓
            Retail의 자유 (1억 단위 / 100% cash 가능 / 3~10년 horizon)
                              ↓
                     C + D combo 진입
```

데이터 / 속도 / 모델 정교화는 institutional의 압도적 우위 영역 — retail이
경쟁할 수 없는 영역. 본 시스템은 이 영역에서 경쟁하지 않는다.

---

## A claim 추가 검증 (information_edge_evidence)

`primary`에 `"A"` 포함 시:

```
1. information_edge_claimed=true 자동 set
2. information_edge_evidence 필수 helper citation
3. confirmation_bias_check:
   Q1. 이 정보 edge가 시장 가격에 이미 반영되었을 가능성은?
   Q2. 시장이 같은 정보를 보고 다른 결론에 도달한 이유는?
   Q3. 이 edge가 false면 어느 falsifier가 trigger되는가?
4. 답변이 generic ("내가 맞다", "시장이 틀렸다")이면 reject
5. fallback 권고: A → B/C/D로 reframe 가능한지 재검토
```


---

## C-claim / D-claim Vague Detection

| pattern | 사유 |
|---|---|
| `"기관이 모른다"` (C-claim vague) | 어느 institutional 제약 (size / IPS / mandate / 유동성) 인지 명시 강제 |
| `"horizon이 다르다"` (D-claim vague) | 분기 P&L 압박이 어떤 mechanism으로 mispricing 만드는지 명시 강제 |

---

## High-Conviction Eligibility

`thresholds.yaml.thesis.edge_source.require_c_or_d_for_high_conviction: true` 시:

- thesis가 단일 종목 5%+ 사이즈를 받으려면 `primary`에 `C` 또는 `D` 중 1+ 필수
- 없으면 verdict=`accepted`라도 Stage 5에서 size 절반 cap
- `metadata.high_conviction_eligibility` 필드로 명시

Stage 4가 cap 직접 적용 안 함 (G6 — sizing은 Stage 5).

---

## Enforcement

| Layer | 내용 |
|---|---|
| `thresholds.yaml.thesis.edge_source` | enum + a_information_warning + require_c_or_d_for_high_conviction |
| `.agents/skills/stage4-thesis-auditor/domain/edge-source-classification.md` | 분류 enum + A claim 확장 검증 + anti-pattern |
| `domains/risk_engine/sizing.py` | high_conviction_eligibility 입력으로 사이즈 cap |
| `.agents/skills/audit-process/SKILL.md` | 주간 audit에서 A 단독 claim 비율 / fallback failure 사례 flag |

---

## Allowed Patterns (예시 thesis 본문)

```
✓ ["C", "D"] — "OO지주 시총 4000억 → 외국계 mandate 최소 5000억으로 entry 어려움 (C).
   분기 P&L 압박 없는 retail horizon이 NAV 좁힘 12~24개월 hold 가능 (D)."

✓ ["B"] — "MSCI Korea Small Cap 편출 통보 (2026-04-15) → index 추종 펀드 강제 매도.
   thesis intact 가정 시 panic discount는 60일 내 회복 사례 존재 (사용자 보유 backtest log)."

✓ ["A", "C"] — "DART@2026-04-30 별도재무제표의 자회사 영업 양수도 첨부 별표 시점 불일치 검출 (A).
   시총 600억 → institutional entry 어려움 (C). information_edge_evidence + confirmation_bias_check 모두 통과."
```

## Forbidden Patterns

```
✗ ["A"] — "내 산업 분석으로 봤을 때 좋아질 것" (generic, no evidence)
✗ ["C"] — "기관이 모른다" (vague, 제약 미명시)
✗ ["D"] — "장기 보면 오를 것" (vague, mechanism 미명시)
```

---

## Cross-references

- 본 문서는 AGENTS.md "3. 엣지 원천 명시" 의 enforcement 상세
- Stage 4 thesis-auditor의 domain/edge-source-classification.md가 절차 상세
- 충돌 시: thresholds.yaml > 본 문서 > skill 본문
