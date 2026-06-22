# 통계적 정직성 (Statistical Honesty)

## 원리

샘플 크기 (N)가 작으면 그 어떤 결과도 alpha의 evidence가 아니다. 18 trade
로 "outperformed market" 주장은 random outcome일 가능성이 압도적. 본
시스템은 N의 충분성을 hard rule로 enforce — N이 부족하면 통계 wording
자체를 산출물에 출력 안 함.

또한 **shadow portfolio counterfactual**로 LLM filter의 부가가치를
지속 검증. 4-tier (Index / Mechanical / LLM-Filtered / Random) paper-trade
benchmark를 4분기 이상 비교 후, LLM-Filtered가 Mechanical보다 일관되게
열위면 self-disable trigger 발동.

---

## Sample Size Hard Rule

`thresholds.yaml.statistics.sample_gates`:

| N (closed trades) | 허용 표현 |
|---|---|
| N < 10 | `INSUFFICIENT_SAMPLE — alpha 주장 금지` |
| 10 ≤ N < 30 | `DIRECTIONAL_SIGNAL — 부호만 인용` |
| 30 ≤ N < 100 | `WEAK_SIGNAL — t-stat 인용 시 p<0.10 필요` |
| N ≥ 100 | `MEANINGFUL_SIGNAL — p<0.05 표준` |

---

## Forbidden Wording (sample size 미충족 시)

`thresholds.yaml.enforcement.forbidden_language.statistical`:

| 차단 표현 | 허용 조건 |
|---|---|
| `"outperformed the market"` | N >= 30 + t-stat 인용 |
| `"alpha confirmed"` | N >= 100 + p < 0.05 |
| `"strategy proven"` | N >= 100 + 4분기 이상 누적 |
| `"beats benchmark"` | sample size + 어느 benchmark 명시 |

매치 substring은 산출물에서 evidence-based phrasing으로 자동 redact.

---

## 4-tier Shadow Portfolio Counterfactual

`thresholds.yaml.statistics.benchmark_tiers`:

| Tier | 의미 | 관리 |
|---|---|---|
| `tier_0_passive_index` | SPY+KOSPI200 50/50 | 매일 종가 join, daily NAV 갱신 |
| `tier_1_mechanical` | macro_config 룰만 적용 score-only top-K | LLM 미사용, deterministic top-K 선정 |
| `tier_2_llm_filtered` | 본 시스템 actual recommendations | Stage 4 accepted 후보 → 사이즈 / 진입 timing 동일 |
| `tier_3_random` | 같은 A∩C universe에서 random K | random seed = ISO date hash |

각 tier는 동일 initial_capital_krw=1억으로 매일 paper trade. 분기/연간
비교 → LLM filter의 부가가치 측정.

---

## Self-Disable Trigger

`thresholds.yaml.statistics.self_disable_trigger`:

```yaml
condition: "tier_2 < tier_1 for 4 consecutive quarters"
action: "alert + require user re-engineering decision"
minimum_quarters_before_check: 4   # 1년 누적 후부터 검사
```

본 trigger 발동 시:
1. `telemetry/audit/disable-trigger.json` 생성
2. brief-author가 brief 첫 줄에 trigger 내용 출력
3. 사용자가 명시적으로 LLM filter를 disable 또는 재조정 결정할 때까지 새 진입 권고 보류

LLM filter가 mechanical보다 부가가치 못 내면 — system 운용 비용 + LLM
hallucination risk + "가짜 정확함" 기만 가능성 모두 부정적. 자동으로
fallback (mechanical only) 권고.

---

## Outcome Audit Frequency

`thresholds.yaml.statistics.outcome_audit_frequency`:

```yaml
weekly:    "process audit (rule violation check)"
quarterly: "outcome vs benchmarks"
annual:    "full review + self-disable check"
```

주간 audit은 **process** (룰 준수 여부) — 결과 무관. 분기 audit은 **outcome**
(4-tier counterfactual). 연간은 self-disable check + 사용자 재참여
의사결정 reminder.

각 audit은 `.agents/skills/audit-process/SKILL.md` 와 `.agents/skills/audit-outcome/SKILL.md` 가 책임.

---

## Enforcement

| Layer | 내용 |
|---|---|
| `thresholds.yaml.statistics` | sample_gates / benchmark_tiers / shadow_portfolio / self_disable_trigger single source |
| `thresholds.yaml.enforcement.forbidden_language.statistical` | wording cutoff 표 |
| `.agents/skills/stage6-brief-author/SKILL.md` | brief 산출 직전 final redact pass — forbidden wording substring 검사 |
| `.agents/skills/audit-process/SKILL.md` | 주간 룰 위반 횟수 집계 |
| `.agents/skills/audit-outcome/SKILL.md` | 분기 4-tier 비교 → tier_2 vs tier_1 outperform check |
| `domains/audit_integrity/main.py` | 4-tier paper trade state 일별 결정론 갱신 ($AUDIT_DIR/shadow-portfolio/state.json) — F-6 으로 구 LLM 스킬 회수 |
| `domains/audit_integrity/init_shadow_state.py` | shadow state 초기화 (`python -m domains.audit_integrity.init_shadow_state`, initial_capital_krw=1억) |

---

## Allowed / Forbidden Wording 예시

```
DENY (N=18)  "Strategy outperformed the market by 4%"
ALLOW (N=18) "Strategy directional signal positive, sample N=18 closed trades, 
              t-stat=1.2, not yet conclusive (need N>=30)"

DENY (N=12, 6 quarters in)  "alpha confirmed, system working"
ALLOW (N=12) "12 closed trades over 6 quarters; tier_2 vs tier_1 cumulative ratio 1.04x; 
              N below 100 → no statistical significance claim possible"

DENY  "Mechanical 룰이 충분, LLM 필요 없음"  (without quarterly outcome audit basis)
ALLOW "Q3 2026 outcome audit: tier_2 (LLM-filtered) -2.1% vs tier_1 (mechanical) +1.8% 
       — 1 quarter only, self-disable threshold (4 consecutive quarters) 미충족"
```

---

## Cross-references

- 본 문서는 AGENTS.md "5. 통계적 정직성" 의 enforcement 상세
- bootstrap.md Section 5.G + thresholds.yaml.statistics single source
- 4-tier paper trade 운영은 audit skills 3개에서 single source로 처리
- 충돌 시: thresholds.yaml > 본 문서 > audit skill 본문
