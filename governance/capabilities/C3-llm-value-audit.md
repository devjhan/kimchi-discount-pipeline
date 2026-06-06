# C3 — 분기 LLM-가치 audit

## Job Story

> **When** LLM 필터가 mechanical baseline 을 분기 누적 수익률로 못 이기면,
> **I want** 시스템이 자동으로 감지하고 self-disable trigger 를 발동하기를,
> **so I can** confirmation bias 로 LLM 필터를 맹신하지 않고, 부가가치 없는 층을 끈다.

시스템 스스로의 가치를 falsify 하는 capability. LLM filter 가 mechanical 보다 못하면
시스템은 자신을 비활성화해야 한다.

## End-to-end trace

```
goal     LLM filter(tier_2)가 mechanical(tier_1) 대비 실제 alpha 를 더하는지 검증
trigger  일별 결정론 NAV 갱신 + 분기 비교 (out-of-band 일정)
engine   domains.audit_integrity.main  — 4-tier shadow portfolio (Index/Mechanical/
         LLM-Filtered/Random) paper-trade NAV 일별 갱신 (실제 broker 호출 0, G9)
skill    investment-audit-outcome  — 분기 누적 비교 (read-only, stat_tests 소비)
output   telemetry/audit/shadow-portfolio-state.json (재생성-불가 증거, append-only)
         + telemetry/audit/outcome-{YYYY-Q}.md
trigger  self-disable: tier_2 < tier_1 4분기 연속
```

## 적용 axiom

- **#5 통계정직** — sample size N 별 허용 표현 hard rule (N<10 alpha 주장 금지 등).

## 성공 / 실패 신호

- ✅ 성공: 4-tier 비교로 LLM 부가가치 정량 검증 · N 부족 시 표현 강등.
- ❌ 실패: N<10 에 "alpha confirmed" · NAV 계산을 LLM 위임 · state 덮어쓰기(G20 위반).

## 관련

- BC: [`../../domains/audit_integrity/AGENTS.md`](../../domains/audit_integrity/AGENTS.md)
- skill: `investment-audit-outcome` (분기) · `investment-audit-process` (주간 룰 위반 집계)
- 결정론 엔진 (LLM 회수): [ADR-0003](../decisions/0003-llm-drafts-python-commits.md)
- statistical honesty 본문: [`../AXIOMS/statistical-honesty.md`](../AXIOMS/statistical-honesty.md)
