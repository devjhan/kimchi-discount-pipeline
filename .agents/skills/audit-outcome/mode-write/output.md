# Mode A — 정상 audit 작성

## 조건

- `$AUDIT_DIR/shadow-portfolio/state.json` 존재 (read 가능)
- 분기 누적 1+ daily snapshot (실제 트레이드 1+ closed)

## 절차

1. shadow-portfolio/state.json read → 각 tier 분기 수익률 계산 (stat_tests helper 호출, G6)
2. tier 비교: tier_2 minus tier_1 / tier_0 / tier_3
3. sample_gate 적용: N(closed trades) 기준 wording 제한 (G19)
4. self-disable check: evaluate_self_disable_trigger → 4분기 연속 열위 시 trigger

## 산출

- `$AUDIT_DIR/outcome-{YYYY-Q}.md`
- trigger 발동 시 `$AUDIT_DIR/disable-trigger.json` 추가

## Verdict 후보

`tier2_outperform` | `tier2_inline` | `tier2_underperform` | `self_disable_triggered`
