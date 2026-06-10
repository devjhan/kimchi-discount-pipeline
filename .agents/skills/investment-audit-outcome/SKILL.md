---
name: investment-audit-outcome
description: Investment 파이프라인 분기 outcome audit. 4-tier shadow portfolio (Index / Mechanical / LLM-Filtered / Random) 의 분기 누적 수익률을 비교해 LLM filter (tier_2)의 부가가치를 검증한다. tier_2 < tier_1 4분기 연속 시 self-disable trigger 발동. $AUDIT_DIR/outcome-{YYYY-Q}.md 산출. shadow portfolio state 자체는 domains.audit_integrity.main 결정론 엔진이 일별 갱신하며, 본 skill은 read-only 비교만 수행.
allowed-tools: Read, Write, Bash, Grep, Glob
---

# investment-audit-outcome — Quarterly Outcome Audit

투자 파이프라인 분기 audit. **4-tier shadow portfolio counterfactual** 비교
로 LLM filter의 부가가치를 통계적으로 측정. 4분기 연속 LLM-Filtered가
Mechanical보다 열위면 self-disable trigger 발동 (statistical-honesty.md
Section 5).

본 skill은 4-tier state를 read-only로 비교만 한다. state 갱신은
`domains.audit_integrity.main` 결정론 엔진 (F-6) 책임.

---

## Reference Contract

**Shared bootstrap (alias 경유 — 단일 source):**
- `$SKILLS_SHARED_DIR/bootstrap.md` — investment 파이프라인 cross-cutting 규약

**프로젝트 root:**
- `CLAUDE.md`
- `$THRESHOLDS_PATH.statistics` (sample_gates / benchmark_tiers / shadow_portfolio / self_disable_trigger)
- `$AXIOMS_DIR/statistical-honesty.md`

---

## Required Identifier

```
quarter: YYYY-Q (예: 2026-Q2). 미지정 시 직전 quarter
```

CLI:

```
/investment-audit-outcome              # 직전 분기
/investment-audit-outcome 2026-Q2
```

---

## Inputs

| 경로 | 내용 |
|---|---|
| `$AUDIT_DIR/shadow-portfolio-state.json` | 현재 4-tier 누적 NAV / trade count / win rate |
| `$AUDIT_DIR/trade-log-{tier}.csv` (tier 4종) | 각 tier의 closed trade history |
| 직전 4 분기 `$AUDIT_DIR/outcome-{YYYY-Q}.md` (.json 보조 파일) | self-disable trigger 4-quarter consecutive 검사 |

---

## Audit Computation

### 1. Quarterly Returns (각 tier)

```
quarter_return_pct = (NAV_end - NAV_start) / NAV_start
```

NAV는 domains.audit_integrity.main 엔진의 daily snapshot에서 read.

### 2. Tier Comparison

```
tier_2_minus_tier_1 = tier_2.quarter_return - tier_1.quarter_return
tier_2_minus_tier_0 = tier_2.quarter_return - tier_0.quarter_return
tier_2_minus_tier_3 = tier_2.quarter_return - tier_3.quarter_return
```

### 3. Sample Size Gate

`$THRESHOLDS_PATH.statistics.sample_gates`:

```
N = 분기 누적 closed trades (tier_2 기준)
if N < 30:  wording 'DIRECTIONAL_SIGNAL — 부호만 인용'
if 30 ≤ N < 100:  wording 'WEAK_SIGNAL — t-stat 인용 시 p<0.10 필요'
if N ≥ 100:  wording 'MEANINGFUL_SIGNAL — p<0.05 표준'
```

t-stat / SE / p-value / bootstrap CI 정량 산출은 모두
`domains.audit_integrity.stat_tests` (Python helper) 가 single source. 본
skill 은 직접 계산하지 않고 helper 결과를 인용한다 (G6).

호출 예 (skill 본체에서 Bash):

```bash
python3 - <<'PY'
import json
from pathlib import Path
from domains.audit_integrity.stat_tests import (
    quarterly_returns, welch_t_test, evaluate_self_disable_trigger,
)
import os
state = Path(os.environ["AUDIT_DIR"]) / "shadow-portfolio-state.json"
a = quarterly_returns(state, "tier_2_llm_filtered")
b = quarterly_returns(state, "tier_1_mechanical")
print(json.dumps({"welch": welch_t_test(a, b)}, ensure_ascii=False, indent=2))
PY
```

citation 형식 (본문에 인용 시):
`STAT@{date}={"t":-1.23,"p":0.21,"n_a":12,"n_b":12,"mean_diff":-0.016,"se_diff":0.013}`

### 4. Self-Disable Trigger Check

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

---

## Output Artifact

```
$AUDIT_DIR/outcome-{YYYY-Q}.md
```

본문 구조:

```markdown
# Outcome Audit — Quarter {YYYY-Q}

## Summary

- period: {start_date} ~ {end_date}
- closed trades (cumulative): N=42
- sample_gate: WEAK_SIGNAL (30 ≤ N < 100)
- verdict: tier_2 < tier_1 (this quarter)
- consecutive quarters tier_2 < tier_1: 2 / 4 (self-disable trigger 미발동)

## Tier-by-Tier Returns

| Tier | name | quarter_return | YTD | cumulative since {init_date} |
|---|---|---|---|---|
| 0 | passive_index (SPY+KOSPI200 50/50) | +2.1% | +5.4% | +18.2% |
| 1 | mechanical (score-only top-K) | +3.4% | +7.1% | +24.5% |
| 2 | llm_filtered (system actual) | +1.8% | +4.6% | +20.1% |
| 3 | random (same A∩C universe) | +0.9% | +3.0% | +15.0% |

## Statistical Wording (sample_gate=WEAK_SIGNAL)

stat_tests.welch_t_test 산출 인용 (1 trade ≠ 1 분기 — 분기 누적 수익률 표본 기반):

- STAT@2026-Q2={"t":-1.18,"df":12,"p_two_sided":null,"n_a":4,"n_b":4,"mean_diff":-0.012,"se_diff":0.0102,"note":"df<30 — sign-only 인용"}
- tier_2 - tier_1 = -1.6%p (음수, 1 quarter)
- tier_2 - tier_0 = -0.3%p (음수, 1 quarter)
- tier_2 - tier_3 = +0.9%p (양수, 1 quarter)

## Self-Disable Trigger

- consecutive_quarters_tier2_below_tier1: 2 (this Q + previous Q)
- threshold: 4
- status: not yet triggered

## Recommendations

(메타 권고만 — config 임계값 조정, lens 평가 패턴 재검토 등.
실제 LLM filter disable 결정은 사용자 명시 후.)
```

verdict enum:
- `tier2_outperform`: tier_2 > tier_1 in this quarter
- `tier2_inline`: tier_2 ≈ tier_1 (within 0.5%p)
- `tier2_underperform`: tier_2 < tier_1
- `self_disable_triggered`: 4 quarters consecutive tier_2 < tier_1
- `insufficient_quarters`: 누적 4분기 미만

---

## Output Mode

### Mode A — outcome audit 작성

조건: shadow-portfolio-state.json 존재 + 직전 분기 동안 daily snapshot 60+ 건 (분기 거래일 60일 가정).

→ 본문 markdown 산출.

### Mode B — 누적 부족

조건: shadow portfolio init 후 1분기 미완료.

→ "insufficient quarters — system 운영 1분기 미만, outcome audit 미산출" 1줄.

### Mode C — state missing

조건: shadow-portfolio-state.json 부재.

→ 즉시 중단, audit-init-shadow-state.py 실행 권고.

---

## Self-Disable Trigger 발동 시 부가 산출

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

---

## Hard Guards

| ID | 적용 |
|---|---|
| G6 | shadow portfolio NAV 자체 재계산 금지 (state read-only) |
| G19 | sample_gate 미충족 시 alpha 주장 wording 자동 redact |
| G20 | outcome audit 덮어쓰기 금지 |

---

## Self-Validation

```
1. shadow-portfolio-state.json read-only로 처리했는가?
2. sample_gate에 따른 wording 룰 정확히 적용했는가?
3. self-disable trigger consecutive count 정확히 4인지 검증했는가?
4. 본문에 forbidden statistical wording 매치 없는가?
5. 출력 경로가 $AUDIT_DIR/outcome-{YYYY-Q}.md (또는 .{N}.md) 인가?
```

---

## Out of Scope

- shadow portfolio state 갱신 (domains.audit_integrity.main 엔진 책임)
- process audit (룰 위반 검사 — investment-audit-process 책임)
- 자동 LLM filter disable 실행 (사용자 명시 결정 후)
