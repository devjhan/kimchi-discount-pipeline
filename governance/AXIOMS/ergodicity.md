# 생존 최우선 (Ergodicity / Survival above Optimization)

## 원리

비-에르고딕 과정에서 **시간평균 ≠ 앙상블평균**. 다수 참여자의 평균
수익률 (앙상블평균)과 단일 참여자가 시간 따라 경험하는 수익률 (시간평균)
은 다르다. 단 한 번의 ruin은 absorbing barrier — 회복 불가능. 따라서
expected return 최대화가 아닌 **기하평균 최대화**가 single objective.

본 시스템은 retail의 단일 자본 (1억 단위)에 대해 시간평균이 앙상블평균보다
열위인 환경 — leverage / 집중 / drawdown 무관심 strategy는 충분히 긴
시간 horizon에서 ruin 확률 1로 수렴. agent의 모든 sizing / cash band /
catalyst 평가는 기하평균을 최대화하는 방향으로 정렬된다.

---

## 본 시스템에서의 의미

- **모든 사이즈는 fractional Kelly** (1/4 ~ 1/2). full Kelly 금지.
  - thresholds.yaml.sizing.kelly.fraction default = 0.25 (quarter-Kelly)
  - thresholds.yaml.sizing.kelly.portfolio_kelly_cap = 0.5 (합산)
- **단일 종목 25% cap** (per-position max).
- **drawdown circuit breaker**: portfolio drawdown -15% 도달 시 모든 사이즈 자동 절반.
- **현금 100% 가능**: regime이 crisis면 cash band = [0.50, 0.90]. 모든 자본 cash 보유가 valid output.
- **default = no action**: 매일 새 후보 0이 정상. 강제 trade signal 양산 = false-positive 양산.

---

## Enforcement (어느 layer에서 적용되는가)

| Layer | 내용 |
|---|---|
| `thresholds.yaml.sizing` | per_position.max_pct=0.25, drawdown_brake.threshold_pct=0.15 |
| `thresholds.yaml.macro.cash_band` | regime별 [min, max] 현금 비중 |
| `scripts/stage5-sizing.py` | G16/G17/G18 enforce — fractional Kelly + cap + brake + cash band 모든 hard guard 적용 |
| `~/.agents/skills/stage6-brief-author/SKILL.md` | brief에 "should buy" / "must hold" forbidden 검사 |
| `~/.agents/skills/audit-process/SKILL.md` | 주간 audit에서 사이즈 위반 / brake 미적용 사례 flag |

---

## Forbidden Patterns

| 위반 | 사유 |
|---|---|
| 단일 종목 30% / 50% / all-in | per_position.max_pct=0.25 위반 |
| Margin / leverage / 신용 사용 | full Kelly 보다 큼, 시간평균 음수화 |
| "이번 한 번만 큰 베팅" | absorbing barrier 무시 — 한 번의 실패 = ruin |
| drawdown 깊어진 후 "본전 회복 위해 더 들어감" (Martingale) | ruin 가속화 |
| "현금은 idle, 무조건 invest" | cash가 portfolio survival의 일부 |

---

## Allowed Patterns

```
- regime=crisis → cash 60~90% 유지, 새 진입 사이즈 max_pct/2로 자동 보정
- 보유 포지션 falsifier 임박 → 사이즈 절반 + 사용자 alert (자동 청산 금지)
- portfolio drawdown -15% → 모든 신규 진입 사이즈 절반 (G17)
- 종목 thesis 변하지 않았어도 사이즈 cap 도달 → 추가 매수 금지
```

---

## Cross-references

- 본 문서는 AGENTS.md "1. 생존 최우선" 의 enforcement 상세
- bootstrap.md Section 5.F (Survival Bounds) + thresholds.yaml.sizing single source
- 충돌 시: thresholds.yaml > 본 문서 > skill 본문
