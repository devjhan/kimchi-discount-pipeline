# C5 — sizing 권고

## Job Story

> **When** portfolio context(총 자본)가 입력돼 있는 상태에서 thesis 후보가 나오면,
> **I want** fractional Kelly % + drawdown circuit breaker 가 반영된 사이즈 권고를,
> **so I can** 한 번의 ruin(absorbing barrier — 회복 불가)을 구조적으로 회피한다.

비-에르고딕 과정에서 시간평균 < 앙상블평균. 기하평균 최대화를 위해 모든 사이즈는
fractional Kelly 로 제한된다. **context 미입력 시 사이즈 출력 보류** (G12).

## End-to-end trace

```
goal     각 후보에 "얼마나" 를 생존 우선 제약 하에서 권고
trigger  Stage 4 thesis candidates 존재 (04-thesis-candidates.json)
stage    Stage 5 sizing — fractional Kelly(1/4~1/2) + asymmetry budget + regime cash band
input    config/user/portfolio.yaml (total_capital_krw — 필수) +
         telemetry/positions/_account/derived-{date}.json (drawdown/cash% 자동 파생)
output   operations/{date}/05-sizing-recommendation.json
guard    context 없으면 omit (G12) · 단일 종목 25% cap · Σ Kelly ≤ 0.5 · drawdown -15% 시 절반
```

## 적용 axiom

- **#1 생존** — fractional Kelly + cap + drawdown circuit breaker.
- **#4 비대칭** — downside_floor / upside_ceiling ≥ 2; 미만이면 reject 또는 size 절반.

## 성공 / 실패 신호

- ✅ 성공: cap 준수 · context 없으면 사이즈 omit · asymmetry ratio 검증.
- ❌ 실패: context 없이 사이즈 출력 · cap 초과 · "potential" 단독 인용(downside 누락).

## 관련

- BC: [`../../domains/risk_engine/AGENTS.md`](../../domains/risk_engine/AGENTS.md) (sizing concern)
- config: `config/user/portfolio.yaml` ([`../procedures/config-files-reference.md`](../procedures/config-files-reference.md))
- 사이즈 cap / asymmetry 규칙: [../../AGENTS.md](../../AGENTS.md) (Hard Guards G12 / G16)
- ergodicity / asymmetry 본문: [`../AXIOMS/ergodicity.md`](../AXIOMS/ergodicity.md) · [`../AXIOMS/asymmetry.md`](../AXIOMS/asymmetry.md)
