# Stat Tests — 통계적 정직성 (axiom #5)

## 모듈 (`stat_tests.py`, stdlib only)

`__all__ = ["welch_t_test", "bootstrap_ci", "quarterly_returns", "evaluate_self_disable_trigger"]`

```python
_mean_var(xs) -> (mean, var)                 # 표본분산 n-1
welch_t_test(a, b) -> dict                    # Welch 2-sample t (이분산)
bootstrap_ci(samples, iters=10_000, seed=42, alpha=0.05) -> dict   # percentile bootstrap of mean (결정론 seed)
quarterly_returns(state_path: Path, tier: str, n_quarters=None) -> list[float]
evaluate_self_disable_trigger(state, gates=None, *, consecutive_required=4, p_max=0.10) -> dict
```

`welch_t_test` 반환 키: `method`/`t`/`df`/`p_two_sided`/`n_a`/`n_b`/`mean_a`/`mean_b`/`var_a`/
`var_b`/`mean_diff`/`se_diff`/`ci_95`/`note`. **p-value/CI 는 `df >= 30` 일 때만** 계산
(`statistics.NormalDist` 근사); 아니면 `note` ("df<30 — sign-only 인용 권장"). `n_a<2` 또는
`n_b<2` 면 `t/df/p = None`. → `stat_tests` 자체 gate 는 `n<2` 와 `df>=30` 두 가지뿐.

## sample-size band (4 band → label)

**라벨은 `stat_tests.py` 가 계산하지 않는다** — read-only outcome skill 의 wording 규칙이며
`governance/thresholds.yaml.statistics.sample_gates` 가 구동:

```yaml
sample_gates:
  n_min_for_directional: 10
  n_min_for_t_stat: 30
  n_min_for_p_010: 30
  n_min_for_p_005: 100
```

| N (closed trades) | label |
|---|---|
| N < 10 | `INSUFFICIENT_SAMPLE` (alpha 주장 금지) |
| 10 ≤ N < 30 | `DIRECTIONAL_SIGNAL` (부호만) |
| 30 ≤ N < 100 | `WEAK_SIGNAL` (t-stat 인용 시 p<0.10) |
| N ≥ 100 | `MEANINGFUL_SIGNAL` (p<0.05) |

canonical 표는 `AGENTS.md` axiom #5 + `governance/AXIOMS/statistical-honesty.md`. forbidden-language
gate 는 `thresholds.yaml.enforcement.forbidden_language.statistical` (`"outperformed the market"`/30,
`"alpha confirmed"`/100, `"strategy proven"`/100, `"beats benchmark"`/30) — G19.

## self-disable trigger (4 분기 연속 mechanical > LLM)

`evaluate_self_disable_trigger` 계산 로직:
- tier_2 (`a`) / tier_1 (`b`) `quarterly_history` flatten
- `a[-i] < b[-i]` 인 trailing 연속 분기 count
- `consec_passed_sign = consec >= consecutive_required`
- `consec_passed_p = (p < p_max and mean_diff < 0)` (df<30 로 p 없으면 None)
- `trigger_armed = consec_passed_sign and consec_passed_p is True`

반환: `consecutive_quarters` / `consecutive_required` / `consec_passed_sign` / `consec_passed_p` /
`p_max` / `trigger_armed` / `rationale` / `welch`. threshold 는
`thresholds.yaml.statistics.self_disable_trigger` (`consecutive_required: 4`, `p_max: 0.10`,
`minimum_quarters_before_check: 4`, `condition: "tier_2 < tier_1 for 4 consecutive quarters AND
Welch p_two_sided < p_max"`).

## read-only skill 소비 (ADR-0003 — 읽되 계산 안 함)

- **`investment-audit-outcome`** (분기): `shadow-portfolio-state.json` + `trade-log-{tier}.csv` read
  → `quarterly_returns` + `welch_t_test` + `evaluate_self_disable_trigger` 호출 (inline `python3`
  Bash block) → 결과를 `STAT@{date}={...}` 로 인용 → `outcome-{YYYY-Q}.md` (+ 발동 시
  `disable-trigger.json`). out-of-scope: state update (엔진), process audit. guard: G6 (NAV 재계산
  금지) / G19 (sample_gate redaction) / G20.
- **`investment-audit-process`** (주간): 7일 trail artifact read → rule violation AP-1..AP-15 scan
  → `process-{YYYY-WW}.md`. out-of-scope: shadow state update (`domains.audit_integrity.main`).
  guard: G6/G7/G20/G21.

두 skill 모두 state update 가 `domains.audit_integrity.main` 소관임을 `Out of Scope` 에 명시 —
ADR-0003 (LLM 은 읽기/draft, Python 이 계산/commit) 의 살아있는 instance.
