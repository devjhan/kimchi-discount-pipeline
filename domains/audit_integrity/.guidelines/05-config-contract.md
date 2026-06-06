# Config — central thresholds.statistics (local config 없음)

audit_integrity 는 **config-free** (`config/` 디렉토리·`*.yaml` 없음 — universe 의 self-contained
config 와 대조). 정량 knob 은 중앙 `governance/thresholds.yaml.statistics` 에.

| 파일 | schema | 역할 | 로더 |
|---|---|---|---|
| (in-package 없음) | — | — | — |
| `governance/thresholds.yaml` | `investment-thresholds-v1` (version 1) | 정량 knob SSoT | `_boundary.load_thresholds()`; init 은 `load_yaml_config(args.config)` |

## thresholds.yaml.statistics 키 (read)

```yaml
statistics:
  sample_gates:                  # outcome skill 이 read (band label — 02-stat-tests.md)
    n_min_for_directional: 10
    n_min_for_t_stat: 30
    n_min_for_p_010: 30
    n_min_for_p_005: 100
  benchmark_tiers:               # init_shadow_state.py 가 tier 명명에 read
    tier_0_passive_index: "SPY+KOSPI200 50/50"
    tier_1_mechanical: "score-only top-K, no LLM"
    tier_2_llm_filtered: "system actual recommendations"
    tier_3_random: "random K from same A∩C universe"
  shadow_portfolio:              # main.py._engine_config + init 가 read
    update_frequency: "daily"
    rebalance_method: "buy-and-hold-snapshot"
    initial_capital_krw: 100000000
    top_k: 5
    max_hold_days: 30
    rebalance_threshold_pct: 0.05
    tier0_tickers: ["US:SPY", "KR:069500"]
  self_disable_trigger:          # outcome skill (evaluate_self_disable_trigger)
    condition: "tier_2 < tier_1 for 4 consecutive quarters AND Welch p_two_sided < p_max"
    consecutive_required: 4
    p_max: 0.10
    minimum_quarters_before_check: 4
  bootstrap: { iters: 10000, seed: 42 }
  outcome_audit_frequency: { ... }   # weekly / quarterly / annual (skill)
```

엔진은 top-level `version` 도 read → envelope `config_version` (default `"unknown"`).

## 책임 분리

- 정량 통계 knob → `governance/thresholds.yaml.statistics` (cross-BC SSoT). audit_integrity 는
  read only.
- band label / forbidden-language 는 **skill-side wording 규칙** (`sample_gates` /
  `enforcement.forbidden_language.statistical` 구동) — 엔진은 N<2 / df≥30 만 gate.

## D-CFG-1 공통 헤더

`governance/directives/12-config-text.md` §D-CFG-1 — 모든 `governance/*.yaml` 은 첫 5줄 내
`version:` + `description:` 선언 (`block_anti_patterns` PreToolUse 강제). thresholds.yaml 준수
(`version: 1` / `last_updated` / `schema`). state-file envelope 은 `base_report_envelope` 로
D-Q-2 5필드 (`schema` / `generated_at` / `date` / `config_path`·`config_version` / `warnings`).

## schema bump 규약

on-disk state schema 는 versioned literal `"investment-shadow-portfolio-state-v1"` (상수
`SCHEMA_VERSION` in `init_shadow_state.py`; `ShadowPortfolioState.from_dict` default 동일).
`state.py.from_dict` 는 forward-tolerant (미지 top-level 키는 `extra` 보존; `cash_krw` /
`quarterly_history` 부재 시 재구성) — 정식 bump 절차 대신의 de-facto 호환 메커니즘. 호환 깨는
변경 시 `vN` 올림.
