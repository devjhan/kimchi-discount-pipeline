# Config — regimes.yaml Single Source

## Schema 헤더 (D-CFG-1 준수)

```yaml
schema: "macro-regimes-v1"
version: 1
description: "..."
last_updated: "YYYY-MM-DD"
```

## 구조

```yaml
thresholds:
  yield_curve: {late_cycle_signal, crisis_signal, ...}
  credit_spread: {mid_cycle_max, late_cycle_min, crisis_min}
  vix: {complacent_max, panic_min}
  breadth: {healthy_min, late_cycle_max, crisis_max}

cash_band:
  early_cycle:  [min, max]
  mid_cycle:    [min, max]
  late_cycle:   [min, max]
  crisis:       [min, max]
  unknown:      [min, max]

regime_shift_alert:
  require_consecutive_days: 3
  notify_user: true
```

## Envelope contract (출력 `00-macro-regime.json`)

- schema: `investment-stage0-macro-regime-v1`
- `regime_decision.regime`: 5 candidates (early_cycle / mid_cycle / late_cycle / crisis / unknown)
- `regime_decision.rationale`: 각 Signal.vote 가 반환한 rationale 리스트
- `regime_decision.votes`: skip 제외한 vote 값 리스트
- `regime_decision.vote_summary`: {regime: count} dict

## thresholds.yaml 와의 책임 분리

- `governance/thresholds.yaml` — cross-cutting 정량 임계값 (sizing, statistics, forbidden_language, catalyst) — macro 키 부재
- `domains/macro/config/regimes.yaml` — stage 0 macro 전용 임계값 — single SSoT

## drift 방지

macro 임계값은 `regimes.yaml` 단독. `application/regime_classify.py` 의 default value (`crisis_signal=-1.0` 등) 는 *fallback only* — yaml 미존재 / 키 누락 시 사용. drift 시 yaml 우선.
