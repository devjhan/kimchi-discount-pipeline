# Stat Tests — 통계적 정직성 (axiom #5)

## 모듈 (`stat_tests.py`, stdlib only)

```python
__all__ = ["welch_t_test", "bootstrap_ci", "quarterly_returns", "evaluate_self_disable_trigger"]
```

`welch_t_test` 반환: `method`/`t`/`df`/`p_two_sided`/`n_a`/`n_b`/`mean_a`/`mean_b`/`mean_diff`/`ci_95`/`note`. **p-value/CI 는 `df >= 30` 일 때만** 계산 (아니면 note: "df<30 — sign-only 인용 권장").

## Sample-size band (4 band → label)

| N (closed trades) | label |
|---|---|
| N < 10 | `INSUFFICIENT_SAMPLE` (alpha 주장 금지) |
| 10 ≤ N < 30 | `DIRECTIONAL_SIGNAL` (부호만) |
| 30 ≤ N < 100 | `WEAK_SIGNAL` (t-stat 인용 시 p<0.10) |
| N ≥ 100 | `MEANINGFUL_SIGNAL` (p<0.05) |

canonical: axiom #5 + `governance/AXIOMS/statistical-honesty.md`. forbidden-language: `thresholds.yaml.enforcement.forbidden_language.statistical`.

## Self-disable trigger (4 분기 연속 mechanical > LLM)

`evaluate_self_disable_trigger` 로직:
- tier_2 / tier_1 `quarterly_history` flatten
- `a[-i] < b[-i]` 인 trailing 연속 분기 count
- `consec_passed_sign = consec >= consecutive_required` (default 4)
- `consec_passed_p = (p < p_max and mean_diff < 0)` (df<30 시 None)
- `trigger_armed = consec_passed_sign and consec_passed_p is True`

threshold: `thresholds.yaml.statistics.self_disable_trigger` (`consecutive_required: 4`, `p_max: 0.10`).

## Read-only skill 소비 (ADR-0003)

- **`investment-audit-outcome`** (분기): state + trade-log read → `quarterly_returns` + `welch_t_test` + `evaluate_self_disable_trigger` (inline `python3`) → 결과 인용 → `outcome-{YYYY-Q}.md` (+ `disable-trigger.json`)
- **`investment-audit-process`** (주간): 7일 trail artifact read → rule violation scan → `process-{YYYY-WW}.md`

두 skill 모두 state update 가 `domains.audit_integrity.main` 소관임을 명시 — ADR-0003 의 살아있는 instance.
