# AXIOMS — 5대 철학

> **원본**: `governance/AXIOMS/asymmetry.md` ~ `statistical-honesty.md` (5파일)
> **본 파일**: agent-readable 인덱스. 우선순위 최상위 — AXIOMS > G1-G22 > D-ID.

| # | 철학 | 1줄 | 원본 파일 |
|---|---|---|---|
| 1 | 생존 최우선 | 기하평균 극대화 — 단일 종목 25% cap, fractional Kelly, drawdown -15% brake, 현금 100% 가능 | `ergodicity.md` |
| 2 | 반증 가능성 | 모든 thesis 는 구체적 falsifier 강제 (time-cap / metric-trigger / event-trigger). vague pattern 자동 reject | `falsifiability.md` |
| 3 | 엣지 원천 명시 | C(구조) + D(시간) 이 본질적 edge — A(정보) 인용 시 추가 검증 + confirmation_bias_check | `edge-source.md` |
| 4 | 비대칭 손익비 | downside_floor / upside_ceiling 비율 < 2 → reject 또는 size 절반 cap. "potential" 단독 금지 | `asymmetry.md` |
| 5 | 통계적 정직성 | N < 10: 주장 금지 / 10≤N<30: 부호만 / 30≤N<100: p<0.10 / N≥100: p<0.05. 4-tier shadow portfolio self-disable | `statistical-honesty.md` |

## Enforcement 요약

| 철학 | 주요 enforcement |
|---|---|
| #1 생존 | `thresholds.yaml.sizing` (Kelly fraction=0.25, per_position.max_pct=0.25, drawdown_brake=-15%), `thresholds.yaml.macro.cash_band` |
| #2 반증 | `thresholds.yaml.thesis` (required_fields, falsifier_categories, vague_patterns_reject), Stage 4 skill `falsifier-validation.md` |
| #3 엣지 | `thresholds.yaml.thesis.edge_source` (enum + a_information_warning + require_c_or_d_for_high_conviction), Stage 4 skill `edge-source-classification.md` |
| #4 비대칭 | `thresholds.yaml.thesis.asymmetry` (min_ratio=2.0, half_size_below_ratio=3.0), Stage 5 sizing |
| #5 통계 | `thresholds.yaml.statistics` (sample_gates, self_disable_trigger), `audit_integrity` BC (4-tier shadow portfolio) |

## AXIOMS 원본 파일이 기술하는 것

각 `governance/AXIOMS/*.md` 는:
- 철학의 **원리** (왜 이 rule 이 존재하는가)
- **본 시스템에서의 의미** (어떻게 구현·적용되는가)
- **Enforcement** (어느 layer 에서 강제되는가: thresholds.yaml / skill / Python)
- **Forbidden / Allowed Patterns** (구체적 예시)
- **Cross-references** (연관 문서 링크)
