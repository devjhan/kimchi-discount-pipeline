# 비대칭 손익비 (Asymmetric Payoff)

## 원리

모든 진입은 **downside_floor / upside_ceiling 비율**로 측정된다. 단순한
"potential" 인용은 thesis 거부 사유. 잠재 수익률만 보고 진입하는 행위는
loss 측면을 무시하는 cognitive bias의 형식 표현.

본 시스템은 진입 전 두 측을 강제 측정:
- **downside_floor**: 가장 합리적인 worst case에서 가격이 어디까지 갈 수 있는가
- **upside_ceiling**: 가장 합리적인 best case에서 가격이 어디까지 갈 수 있는가

비율 (ceiling / floor) 이 작으면 (< 2), 진입 정당화 어려움. fractional
Kelly 공식 자체가 이 비율을 입력으로 받음 — asymmetry 없으면 사이즈 0.

---

## 본 시스템에서의 의미

### 비율 cutoff

`thresholds.yaml.thesis.asymmetry`:

```yaml
asymmetry:
  min_ratio: 2.0                 # downside_floor / upside_ceiling
  reject_below_min: false         # false면 size 절반 cap (true면 reject)
  half_size_below_ratio: 3.0      # ratio < 3 시 사이즈 절반
```

### Portfolio-level barbell

CLAUDE.md "4. 비대칭 손익비" 명시:

```
safe sleeve     : 현금 + 단기채 + low-vol 배당
optional sleeve : high-conviction asymmetric bet
middle sleeve   : medium-vol broad-market
```

각 sleeve 비중 cap은 사용자 portfolio context (volatility tolerance) 따라
조정. 1차 운용은 thresholds.yaml.sizing의 per_position.max_pct=0.25 +
portfolio_kelly_cap=0.5로 implicit barbell 구현.

---

## Stage 4 vs Stage 5 책임 분리

| 단계 | 책임 |
|---|---|
| **Stage 4 thesis-auditor** | downside_floor / upside_ceiling 본문 작성 (helper citation 포함). ratio 산출 안 함 (G6) |
| **Stage 5 sizing** | downside_floor / upside_ceiling parse → ratio 계산 → fractional Kelly 산출 + cap 적용 |

이 분리는 **G6 (수치 계산 LLM 위임 금지)** 의 핵심 enforcement. Stage 4
LLM이 ratio 직접 산출 시 helper-side validation 우회 가능 — 따라서
asymmetry_score.computed_ratio=null 강제, computed_by='stage5_helper_pending'
marker.

---

## downside_floor 작성 강제 기준

```
- 가격 단위: % (현재 가격 대비) 또는 KRW 절대값
- rationale: 어떤 시나리오에서 floor에 도달하는가 (예: NAV 할인 80% 확대)
- source_citation: helper script 인용 (DART NAV / financial 캐시 등)
```

`undefined`, `unknown`, `to be determined` 류 wording 금지. 측정 helper
미가용 시 needs_user_decision으로 escalate.

---

## upside_ceiling 작성 강제 기준

```
- 가격 단위: % 또는 KRW 절대값
- rationale: 어떤 시나리오에서 ceiling에 도달하는가 (예: NAV 할인 평균 회귀 + 자사주 소각 누적)
- source_citation: helper script 인용
```

"하늘이 한도", "moonshot", "unlimited upside" 류 wording 금지. ceiling은
realistic best case이지 fantasy가 아니다.

---

## fractional Kelly 산출 (Stage 5)

```
b = upside_pct / downside_pct  (asymmetry_ratio)
p = 0.5 (보수적 base, 본 시스템은 win prob 추정에 hubris 안 둠)
q = 1 - p = 0.5

raw_kelly = p - q/b  (= 0.5 - 0.5/b)
fractional_kelly = raw_kelly × kelly.fraction (default 0.25)

if asymmetry_ratio < min_ratio:
    if reject_below_min:
        verdict = rejected_low_asymmetry
    else:
        verdict = size_recommended_half_cap (size /= 2)

if asymmetry_ratio < half_size_below_ratio:
    proposed /= 2  (additional half)

proposed = min(proposed, per_position.max_pct=0.25)
```

`scripts/stage5-sizing.py` 의 `compute_fractional_kelly()` 함수가 single
implementation point.

---

## Enforcement

| Layer | 내용 |
|---|---|
| `thresholds.yaml.thesis.asymmetry` | min_ratio / reject_below_min / half_size_below_ratio |
| `~/.claude/skills/investment-stage4-thesis-auditor/domain/thesis-fields-format.md` | downside_floor / upside_ceiling 본문 schema |
| `scripts/stage5-sizing.py` | extract_asymmetry_ratio() + compute_fractional_kelly() + cap chain |
| `~/.claude/skills/investment-stage6-brief-author/SKILL.md` | brief에 ratio + cap 적용 사유 1줄 표시 |

---

## Forbidden Patterns

```
✗ "potential 30%" 단독 (downside 미측정)
✗ "최대 100% 가능" (ceiling만, floor 없음)
✗ "잘 되면 N배" (정량 floor / ceiling 부재)
✗ Stage 4 LLM이 asymmetry_ratio 직접 산출 (G6)
✗ "downside는 별로 없을 것" (정량 측정 없음)
```

## Allowed Patterns

```
✓ downside_floor: "-30%" + rationale + DART citation
  upside_ceiling: "+120%" + rationale + DART citation
  ratio 계산은 Stage 5가 = 4.0
  → fractional_kelly = 0.094, per_position cap 미적용

✓ downside_floor: "-50%" + rationale
  upside_ceiling: "+80%"
  ratio = 1.6 < min_ratio=2.0
  → reject_below_min=false → size 절반 cap (verdict=size_recommended_half_cap)

✓ asymmetry_ratio 계산 못 한 경우 (downside 측정 helper 미구현)
  → verdict=needs_user_decision, Stage 5 사이즈 산출 보류
```

---

## Cross-references

- 본 문서는 CLAUDE.md "4. 비대칭 손익비" 의 enforcement 상세
- bootstrap.md Section 4 (G5 hard guard) + thresholds.yaml.thesis.asymmetry single source
- 충돌 시: thresholds.yaml > 본 문서 > skill 본문
