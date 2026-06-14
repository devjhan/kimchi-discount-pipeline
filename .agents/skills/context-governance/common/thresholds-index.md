# thresholds.yaml — 정량 임계값 SSoT

> **원본**: `governance/thresholds.yaml` (212줄, `version: 1`, `schema: investment-thresholds-v1`)
> **본 파일**: agent-readable 키 구조 인덱스. 수치 인용 금지 — 항상 `governance/thresholds.yaml` 원본 read.

## 키 구조

### thesis (Stage 4 Thesis Discipline Gate)
```
thesis.required_fields           → [entry_catalyst, falsifier, time_horizon_months, edge_source, asymmetry_score]
thesis.falsifier_categories      → time_cap (max_months: 36), metric_trigger, event_trigger
thesis.falsifier_vague_patterns_reject → 자동 reject 패턴 목록
thesis.edge_source               → enum [A,B,C,D] + a_information_warning + require_c_or_d_for_high_conviction
thesis.asymmetry                 → min_ratio: 2.0, half_size_below_ratio: 3.0
thesis.time_horizon_months       → min: 6, max: 60, typical: [12, 36]
```

### expiry_alert (Stage 5d Thesis Expiry Monitor)
```
expiry_alert.tiers               → notice(90d) / warn(30d) / expired(0d) / overdue(-30d)
expiry_alert.surface_in_brief    → brief 본문 표시 여부
```

### sizing (Stage 5 Sizing)
```
sizing.kelly                     → fraction: 0.25 (quarter-Kelly), portfolio_kelly_cap: 0.5
sizing.per_position              → max_pct: 0.25, min_pct: 0.02
sizing.drawdown_brake            → threshold_pct: -15%, action: "halve_all_sizes", reset: +5%
sizing.requires_user_input       → portfolio_context: true, output_size_without_input: false
```

### falsifier (Stage 5b Falsifier Proximity)
```
falsifier.proximity_bands        → low_max: 0.5, medium_max: 0.9
falsifier.alert_channels         → high: [push_notification]
```

### enforcement (Cross-cutting)
```
enforcement.forbidden_language   → recommendation / statistical / valuation 차단 문구
enforcement.numbers_evidence_required → citation_format: "{source}@{ISO_timestamp}={value}"
enforcement.external_signal      → only_via_explicit_ingest_command: true
enforcement.default_action       → most_days_no_new_candidate: true
```

### statistics (Statistical Honesty + Self-Disable)
```
statistics.sample_gates          → n_min_for_directional:10 / t_stat:30 / p_010:30 / p_005:100
statistics.benchmark_tiers       → tier_0~3 (Index / Mechanical / LLM-Filtered / Random)
statistics.shadow_portfolio      → top_k:5, max_hold_days:30, initial_capital_krw: 1억
statistics.self_disable_trigger  → 4 consecutive quarters tier_2 < tier_1, Welch p < 0.10
statistics.bootstrap             → iters: 10000, seed: 42
```

## 주의

- `thresholds.yaml` 의 stage 0/1/2/3 섹션은 완전 이전됨 — 각 BC `config/` 로 migration 완료
  - Stage 0 (macro): `domains/macro/config/regimes.yaml`
  - Stage 1 (universe): `domains/universe/config/`
  - Stage 2 (screener): `governance/policy/profiles/global/quality_floor/v1.yaml` + `governance/policy/strategies/default/v1.yaml`
  - Stage 3 (catalyst): `domains/catalyst/config/detectors.yaml`
- `thresholds.yaml` 에 남은 것은 **cross-BC 공통 정량** (thesis / sizing / falsifier / enforcement / statistics)
