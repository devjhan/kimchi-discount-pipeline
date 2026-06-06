# ADR-0005 — `_boundary` = 유일 infra-import 게이트 → typed adapter factory

`status: Accepted`
`date: 2026-06-06`
`refs: D-CORE-4, D-CORE-7, D-ARCH-3, D-ARCH-4, screener/.guidelines/05-boundaries.md`

## Context

각 BC 의 외부 I/O 의존 (DART / KIS / Yahoo / FRED / 파일 / 경로) 이 application·domain
코드에 흩어지면 vendor 교체·테스트 stub·경계 강제가 불가능하다. 한편 의존을 한 파일
(`_boundary.py`) 로 모으자 그 파일이 path·time·citation·env·envelope·external-client 등
5~7 무관 concern 을 끌어안은 god-module (SPOF) 이 됐다 (사용자 지적).

## Decision

BC 당 **`_boundary.py` 단일 infra-import 게이트** 를 유지하되, god-module 이 아니라 **narrow
Protocol port 를 주입하는 typed adapter factory** 로 진화시킨다:

- `application/` · `domain/` 은 `infrastructure.*` 를 직접 import 하지 않는다 — `main()`
  composition root 가 `_boundary` 에서 구성한 port 를 주입받는다.
- 무관 concern 은 narrow port 로 추출 (CitationPort / ClockPort / DisclosureSourcePort /
  KisAccountPort). 선례: F-13 LLM port → [D-CORE-7] (evergreen 승격); F-16/F-17.

HOW (포트 추출 절차·템플릿) 의 SSoT 는 `domains/screener/.guidelines/05-boundaries.md`
"Ports & Adapters" 절 — **복사 금지, 참조만.** 본 ADR 은 WHY 만.

## Consequences

- fitness test 가 강제: `infrastructure` import 은 `_boundary.py` 만 (불변식 C,
  `tests/architecture/test_boundary_gate.py`).
- **미전환 잔여**: macro/policy/risk_engine 의 application·domain 이 아직 `_boundary` 를
  직접 import (screener 전용 Phase-0 목표) → fitness test 에서 BC 별 `xfail` 로 추적,
  전환되면 자동 green.

## Alternatives considered

- **BC 마다 자유 infra import** — 기각. 변경증폭 + vendor lock 분산 + 경계 강제 불가.
- **`_boundary` 삭제** — 기각. 단일 게이트가 곧 경계 강제 수단.

## Supersedes / Superseded-by

(없음)
