# C2 — 보유 포지션 falsifier 모니터링

## Job Story

> **When** 보유 thesis 가 자신의 falsifier trigger 에 근접하면,
> **I want** 일일 근접도 알림(T-90 / T-30 / T-0 / T+30 milestone)을,
> **so I can** 만료됐거나 깨진 thesis 를 무의식적으로 계속 보유하지 않는다.

thesis 는 반증 trigger 없이는 thesis 가 아니라 narrative (axiom #2). 보유 포지션의
falsifier proximity 를 일단위로 감시한다.

## End-to-end trace

```
goal     보유 포지션마다 "내 thesis 가 언제·무엇으로 깨지나" 를 일별로 가시화
trigger  보유 포지션 존재 (telemetry/positions/{ticker}/thesis.json)
stages   5a thesis_sync       04-thesis-candidates → positions/{ticker}/thesis.json (결정론 파생)
         5b falsifier_proximity  metric/time falsifier 근접도
         5c event_falsifier_linker  event_trigger × Stage3 catalyst join
         5d thesis_expiry_monitor  time_horizon_months 추적 (multi-tier alert)
BC       domains/risk_engine (monitor concern — 전부 결정론)
output   telemetry/positions/{ticker}/drift-{date}.md · expiry-{date}.md
         + operations/{date}/05b-falsifier-proximity.json · 05d-thesis-expiry.json
```

## 적용 axiom

- **#2 반증가능성** — time-cap / metric-trigger / event-trigger 의 구체적 falsifier 강제.
- **#1 생존** — 깨진 thesis 조기 인지 = drawdown 누적 방지.

## 성공 / 실패 신호

- ✅ 성공: falsifier 근접 시 정확한 milestone alert · vague falsifier 사전 reject.
- ❌ 실패: vague falsifier("실적 나쁘면") 통과 · 만료 thesis 미감지 · proximity 계산을 LLM 위임.

## 관련

- BC: [`../../domains/risk_engine/AGENTS.md`](../../domains/risk_engine/AGENTS.md)
- thesis 작성 게이트: skill `investment-stage4-thesis-auditor`
- 결정론 산식 (LLM 위임 금지): [ADR-0003](../decisions/0003-llm-drafts-python-commits.md)
- falsifiability 본문: [`../AXIOMS/falsifiability.md`](../AXIOMS/falsifiability.md)
