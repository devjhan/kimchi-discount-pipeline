# Config — central thresholds.statistics (local config 없음)

audit_integrity 는 **config-free** (`config/*.yaml` 없음). 정량 knob 은 중앙 `governance/thresholds.yaml.statistics` 에.

| 파일 | schema | 역할 | 로더 |
|---|---|---|---|
| (in-package 없음) | — | — | — |
| `governance/thresholds.yaml` | `investment-thresholds-v1` | 정량 knob SSoT | `_boundary.load_thresholds()` |

## thresholds.yaml.statistics 키 (read)

```yaml
statistics:
  sample_gates:
    n_min_for_directional: 10
    n_min_for_t_stat: 30
    n_min_for_p_010: 30
    n_min_for_p_005: 100
  benchmark_tiers:
    tier_0_passive_index: "SPY+KOSPI200 50/50"
    tier_1_mechanical: "score-only top-K, no LLM"
    tier_2_llm_filtered: "system actual recommendations"
    tier_3_random: "random K from same A∩C universe"
  shadow_portfolio:
    update_frequency: "daily"
    initial_capital_krw: 100000000
    top_k: 5
    max_hold_days: 30
    rebalance_threshold_pct: 0.05
    tier0_tickers: ["US:SPY", "KR:069500"]
  self_disable_trigger:
    consecutive_required: 4
    p_max: 0.10
    minimum_quarters_before_check: 4
  bootstrap: { iters: 10000, seed: 42 }
```

## 책임 분리

- 정량 통계 knob → `governance/thresholds.yaml.statistics` (cross-BC SSoT). read only.
- band label / forbidden-language 는 **skill-side wording 규칙** — 엔진은 N<2 / df≥30 만 gate.

## D-CFG-1 공통 헤더

state-file envelope 은 `base_report_envelope` 로 D-Q-2 5필드 (`schema` / `generated_at` / `date` / `config_path`·`config_version` / `warnings`).

## Schema bump 규약

on-disk state schema `SCHEMA_VERSION = "investment-shadow-portfolio-state-v1"`. `from_dict` 는 forward-tolerant (미지 top-level 키 `extra` 보존; 부재 시 재구성). 호환 깨는 변경 시 `vN` 올림.
