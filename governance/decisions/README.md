# Architecture Decision Records (ADR) — 영구 결정 레지스터

`schema: investment-adr-index-v1`
`last_updated: 2026-06-10`

본 디렉토리는 **비자명한 구조 결정의 영구 ledger** 다. `governance/AXIOMS/`(왜 — 투자
철학) · `governance/specs/`(무엇 — 계약) · `governance/directives/`(어떻게 — 코딩) 와
나란히, **"왜 이 구조인가 / 왜 이건 안 하는가"** 라는 *결정 근거* 축을 담는다.

`architecture-review-findings-2026-06.md` (transient backlog) 와의 본질적 차이:
**ADR 은 append-only 다 — 절대 삭제하지 않는다.** 틀린 결정은 지우지 않고 후속 ADR 로
`Superseded` 표시한다 (기각 기록 `Rejected-proposal` 도 영구 보존 — 재제안 방지).
backlog 는 "할 일", ADR 은 "내린 판단". 할 일이 끝나며 도출된 *영구 판단* 은 이리로 승격
(선례: F-13 LLM port → D-CORE-7; findings §4 "승격 금지" 의 정확한 대상이 본 레지스터).

> ADR 은 SSoT 를 **복사하지 않는다.** G-rule (`specs/hard-guards.md`) · D-CORE / D-ARCH
> (`directives/`) · spec (`specs/`) 은 ID 로 cross-ref 만 한다. 결정 *본문* 은 ADR 한 곳에만
> 존재하고, 다른 문서(per-BC `AGENTS.md`, `pipeline-overview.md`)는 1줄 포인터만 남긴다.

---

## 인덱스

| ADR | 제목 | status | 관련 |
|---|---|---|---|
| [0001](0001-deployment-residency-local-primary.md) | Deployment residency = 로컬 primary | Accepted | `specs/deployment-residency.md` (SSoT), G9 |
| [0002](0002-governance-config-ownership-axis.md) | governance/config 분리 = 소유·버전관리 축 (파일 포맷 아님) | Accepted | [D-ARCH-1](../directives/05-architecture.md) |
| [0003](0003-llm-drafts-python-commits.md) | 결정론 계산은 LLM 위임 안 함 (LLM 초안 · Python commit) | Accepted | G6 (SSoT), D-CORE-7 |
| [0004](0004-bounded-context-split-criteria.md) | BC 통폐합 기준 — 수직 병합 기각 | Accepted | [D-ARCH-2](../directives/05-architecture.md), [0006](0006-fat-contract-isp.md) |
| [0005](0005-boundary-ports-and-adapters.md) | `_boundary` = 유일 infra-import 게이트 → typed adapter factory | Accepted | D-CORE-4/7, [D-ARCH-4](../directives/05-architecture.md) |
| [0006](0006-fat-contract-isp.md) | Fat-contract ISP — `EnrichCutoffProfile` 단일 정책 단위 | Accepted | [D-ARCH-2](../directives/05-architecture.md) |
| [0007](0007-risk-engine-no-concern-reorg.md) | risk_engine — 물리 concern 서브패키지 reorg 기각 | Rejected-proposal | [D-ARCH-2](../directives/05-architecture.md) |
| [0009](0009-storage-topology.md) | Storage topology — 재생성 가능성·수명·소유 축 | Accepted | [D-ARCH-1](../directives/05-architecture.md) |
| [0010](0010-claude-code-to-zed-migration.md) | Claude Code → Zed Agent 마이그레이션 (F-13 vendor swap) | Accepted | `infrastructure/llm/` (SSoT), `specs/deployment-residency.md`, [D-CORE-7](../directives/00-principles.md) |

---

## ADR 템플릿

새 구조 결정 (기각 포함) 은 다음 형식으로 `NNNN-kebab-title.md` 추가 + 위 인덱스 1줄:

```markdown
# ADR-NNNN — 제목

`status: Accepted`            # Accepted | Superseded | Rejected-proposal
`date: YYYY-MM-DD`
`refs: G6, D-ARCH-2, ...`     # ID cross-ref (본문 복사 금지)

## Context
어떤 상황·압력에서 이 결정이 필요했나 (배경 + 제약).

## Decision
무엇을 하기로/안 하기로 했나 (한 문장 + 근거).

## Consequences
이 결정이 강제하는 것 / 포기하는 것 / 후속 영향.

## Alternatives considered
검토 후 버린 대안 + 버린 이유 (재제안 방지).

## Supersedes / Superseded-by
(있으면) 대체 관계.
```

## status 범례

| status | 의미 |
|---|---|
| **Accepted** | 현재 유효한 결정. |
| **Superseded** | 후속 ADR 로 대체됨. `Superseded-by: NNNN` 명시, **삭제 금지**. |
| **Rejected-proposal** | "하지 말 것" 의 영구 기록 — 검토 후 기각된 제안 (재제안 방지). |

## 새 ADR 작성 트리거 ([D-ARCH-6](../directives/05-architecture.md))

파일 위치 / 모듈 통폐합 / 중앙-분산 / 의존 방향 / 포트 추출 등 **비자명한 구조 판단** 이
나오면, 에이전트에 매번 재질문하지 말고 (a) 기존 ADR 조회 → (b) 커버 안 되면 새 ADR 작성.
이것이 "휘발적 판단 → 영구 자산" 의 핵심.
