# ADR-0003 — 결정론 계산은 LLM 위임 안 함 (LLM 초안 · Python commit)

`status: Accepted`
`date: 2026-06-06`
`refs: G6, D-CORE-7`

## Context

LLM 은 비결정적이고 환각 위험이 있다. 정량 계산 (NAV / 수익률 / drift / version /
사이즈 / Kelly) 을 LLM 에 맡기면 같은 입력이 다른 출력을 내고, 감사·재현이 불가능해진다.
이는 5대 철학 #5 (통계적 정직성) · #1 (생존) 과 직접 충돌한다.

## Decision

**모든 결정론 계산은 Python 코드가 소유한다. LLM 은 정성 판단·초안만 생산한다.**
LLM↔결정론 경계는 JSON schema envelope (vendor-neutral seam). 구조적 사례:

- **audit_integrity (F-6)**: 4-tier shadow portfolio NAV/수익률은 `domains.audit_integrity`
  결정론 엔진이 일별 갱신 — 구 LLM 스킬에서 회수.
- **policy (F-10)**: LLM (`policy-profiler` 스킬) 은 profile *draft* 만; commit /
  drift / version / provenance 산술은 `domain/commit_gate.py` 결정론. **스킬은 commit 안 함.**

본 ADR 은 그 *구조적 근거와 사례* 를 기록한다. 규칙 본문 SSoT 는 hard guard **G6** (복사
금지 — ID cross-ref 만).

## Consequences

- LLM 스킬은 산출물 commit 권한이 없다 (draft → 결정론 commit 단계 분리).
- 새 LLM 단계 추가 시 "이 계산이 결정론인가?" 를 먼저 묻고, 결정론이면 Python 으로.
- LLM 런타임은 단일 port (`infrastructure/llm` dispatcher) 경유 → [D-CORE-7].

## Alternatives considered

- **LLM end-to-end (research + commit)** — 기각. G6 위반, 재현·감사 불가, drift 가 "의도"
  인지 "LLM 분산" 인지 식별 불가.

## Supersedes / Superseded-by

(없음)
