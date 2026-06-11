# Output Template — audit-outcome

경로: `$AUDIT_DIR/outcome-{YYYY-Q}.md`

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

## verdict enum

- `tier2_outperform`: tier_2 > tier_1 in this quarter
- `tier2_inline`: tier_2 ≈ tier_1 (within 0.5%p)
- `tier2_underperform`: tier_2 < tier_1
- `self_disable_triggered`: 4 quarters consecutive tier_2 < tier_1
- `insufficient_quarters`: 누적 4분기 미만
