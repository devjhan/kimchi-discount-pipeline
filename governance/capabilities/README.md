# Capability Map — 의도(intent) layer

`schema: investment-capability-map-v1`
`last_updated: 2026-06-06`

본 디렉토리는 시스템의 **"누구에게 / 무슨 결과를"** 축이다. `AXIOMS/`(왜) ·
`specs/`(무엇-계약) · `directives/`(어떻게-코딩) 가 *구현자/에이전트* 를 향한다면, 여기는
**운용자(=사용자 본인)의 목표에서 출발해 시스템 부품으로 내려가는 trace** 다. AXIOMS 의
추상 철학과 `config-files-reference` 의 평면 룩업표 사이에 빠져 있던 연결 층.

각 capability 파일은 **Job Story** (`When [상황], I want [동기], so I can [결과]`) 를 머리말로,
그 아래 `goal → trigger → stage → BC → config → output` end-to-end trace + 적용 axiom +
성공/실패 신호를 담는다. (classic "As a [역할]" user story 대신 Job Story — 1인 운용 도구에
적합.) **새 fact 도입 금지** — 기존 doctrine(AXIOMS / hard-guards §1 / pipeline-overview /
SKILL.md) 의 *합성* 일 뿐.

> 핵심 철학: **Default = No Action.** 대부분의 capability 는 대부분의 날에 "결과 없음" 이
> 정상 출력이다. 매일 시그널이 나오면 그것은 노이즈를 만드는 시스템이다.

---

## 마스터 표

| ID | Capability | Job Story (요약) | 적용 axiom | entry → output |
|---|---|---|---|---|
| [C1](C1-daily-brief.md) | 일일 go/no-go brief | 조용한 날 자신있는 "no action" → 침묵을 신호로 신뢰 | #1 #5 | Stage6 skill → `operations/{date}/daily-brief.md` |
| [C2](C2-position-monitoring.md) | 보유 falsifier 모니터링 | falsifier 근접 시 알림 → 만료 thesis 미보유 | #2 #1 | Stage5a~5d → `telemetry/positions/{ticker}/drift-{date}.md` |
| [C3](C3-llm-value-audit.md) | 분기 LLM-가치 audit | LLM이 mechanical 못 이기면 self-disable | #5 | `audit_integrity` → `telemetry/audit/outcome-{Q}.md` |
| [C4](C4-external-signal-intake.md) | 외부 신호 intake | 외부 의견을 fact-only로만 → thesis 즉시오염 방지 | #3 | `/ingest-external-signal` → `config/signals/{ticker}/` |
| [C5](C5-sizing-recommendation.md) | sizing 권고 | context 있을 때만 fractional Kelly → ruin 회피 | #1 #4 | Stage5 → `operations/{date}/05-sizing-recommendation.json` |
| [C6](C6-macro-regime-gate.md) | macro regime gate | regime별 cash band → 생존 우선 노출 결정 | #1 | Stage0/0a → `operations/{date}/00-macro-regime.json` |

axiom 번호: #1 생존 · #2 반증가능성 · #3 엣지원천 · #4 비대칭 · #5 통계정직
([AXIOMS/](../AXIOMS/)).

---

## 검증 흐름 (capability 가 따르는 제약 계층)

```
L1 생존 / Macro Regime (C6)        → cash band
  L2 보유가능성 / Quality           ┐
  L3 사냥터 / Universe              │ A ∩ C
    L4 방아쇠 / Catalyst
      Thesis Gate → Sizing (C5) → Brief (C1)
보유 포지션:  Monitoring (C2)        (일별 falsifier 근접)
out-of-band:  Signal intake (C4) · LLM-value audit (C3)
```

상세 파이프라인 흐름: [`../pipeline-overview.md`](../pipeline-overview.md).
구조 결정 근거: [`../decisions/`](../decisions/README.md).
