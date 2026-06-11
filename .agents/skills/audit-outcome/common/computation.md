# Audit Computation — audit-outcome

## 1. Quarterly Returns (각 tier)

```
quarter_return_pct = (NAV_end - NAV_start) / NAV_start
```

NAV는 `domains.audit_integrity.main` 엔진의 daily snapshot에서 read.

## 2. Tier Comparison

```
tier_2_minus_tier_1 = tier_2.quarter_return - tier_1.quarter_return
tier_2_minus_tier_0 = tier_2.quarter_return - tier_0.quarter_return
tier_2_minus_tier_3 = tier_2.quarter_return - tier_3.quarter_return
```

## 3. Sample Size Gate

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

## Inputs

| 경로 | 내용 |
|---|---|
| `$AUDIT_DIR/shadow-portfolio-state.json` | 현재 4-tier 누적 NAV / trade count / win rate |
| `$AUDIT_DIR/trade-log-{tier}.csv` (tier 4종) | 각 tier의 closed trade history |
| 직전 4 분기 `$AUDIT_DIR/outcome-{YYYY-Q}.md` (.json 보조 파일) | self-disable trigger 4-quarter consecutive 검사 |
