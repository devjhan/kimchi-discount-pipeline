# Agent Harness 보완 계획 v4 — Skill-First Context Injection + 100줄 하드캡 (2026-06-11)

> **성격**: Claude Code → Zed 마이그레이션(ADR-0027)의 잔여 gap 보완. Zed 1.6.3 "Rules to Skills migration"(#58278)에 정렬.
> **v4 변경**: (1) `investment-` prefix 전면 제거, (2) `capabilities/`·`decisions/` README도 skill 흡수, (3) 모든 SKILL.md 100줄 하드캡 + 서브디렉토리 활용 인덱스화.

---

## 0. 요약

| # | 보완 축 | 우선순위 | 작업량 |
|---|---|---|---|
| **S1** | Context Skills 8종 신설 | **P0** | L |
| **S2** | Root AGENTS.md → Skill Index (180줄) | **P0** | M |
| **S3** | 기존 9종 Skill → 100줄 하드캡 재구성 | **P0** | L |
| **S4** | `investment-` prefix 전역 제거 | **P0** | M |
| **S5** | Pre-commit 자동화 | **P1** | M |
| **S6** | Output Validation Gate | **P2** | L |
| **S7** | Runtime Invariant Monitor | **P3** | M |
| **S8** | Vendor Capability Abstraction | **P3** | M |

---

## 1. Skill 네이밍 컨벤션 (v4)

`investment-` prefix 전면 제거. Layer로만 구분:

```
{layer}-{role}

Layer:
  stage{N}  = pipeline stage task
  context   = domain knowledge injection
  audit     = audit/review task
  ingest    = external signal intake
  policy    = policy governance task
  contract  = shared bootstrap (bootstrap.md)
```

| Old (v3) | New (v4) |
|---|---|
| `investment-context-directives` | `context-directives` |
| `investment-context-screener` | `context-screener` |
| `investment-stage4-thesis-auditor` | `stage4-thesis-auditor` |
| `investment-audit-outcome` | `audit-outcome` |
| `investment-ingest-external-signal` | `ingest-external-signal` |
| `investment-policy-profiler` | `policy-profiler` |

---

## 2. SKILL.md 100줄 하드캡 규칙

### 규칙

- **하드캡**: 모든 SKILL.md 본문(frontmatter 제외)은 **100줄을 초과할 수 없다**.
- **권장**: 50줄 내외 유지.
- **초과 시**: 상세 내용을 서브디렉토리 `domain/` 또는 `reference/` 로 분산.

### SKILL.md 표준 구조 (50~100줄)

```markdown
---
name: {skill-name}
description: {1~2줄 요약}
---

# {skill-name}

{2~3줄 — 언제 invoke 하는가}

## 선행 읽기

1. `domain/{file}.md` — {한 줄}
2. `domain/{file}.md` — {한 줄}
...

## 핵심 불변식

- {1줄}
- {1줄}

## 처리 흐름 (또는 실패 패턴)

1. {step}
2. {step}
...

## 산출물

- `{path}` ({schema})

## Out of Scope

- {bullet}
```

### 서브디렉토리

| 디렉토리 | 용도 |
|---|---|
| `domain/` | 상세 schema, validation rule, 분류 체계, 처리 절차 |
| `reference/` | external contract, config 예시, 템플릿 |

### 적용 대상

- **신규 8종 Context Skill** — 처음부터 100줄 이내로 작성
- **기존 9종 Skill** — 재구성하여 100줄 이내로 축소 (현재 최대 250줄)

---

## 3. Context Skills (신규 8종)

### 3.1 `context-directives` (~80줄)

코딩 컨벤션 주입. 7개 directive 파일의 D-ID 요약을 인라인 1~2줄씩 포함.

### 3.2 BC Context Skills 7종 (각 ~60줄)

`context-macro`, `context-universe`, `context-screener`, `context-catalyst`, `context-risk`, `context-policy`, `context-audit`

각 skill:
- 해당 BC의 `AGENTS.md` + `.guidelines/` 파일을 **선행 읽기 목록**으로 나열
- 핵심 불변식 2~3개 (1줄씩)
- 전형적 실패 패턴 2~3개
- 본문은 인덱스 역할만 — 상세는 원본 파일 참조

### 3.3 흡수 대상

| 파일 | 처리 |
|---|---|
| `governance/capabilities/README.md` | → `context-directives` 선행 읽기 목록에 포함. 파일 삭제. |
| `governance/decisions/README.md` | → `context-directives` 선행 읽기 목록에 포함. 파일 삭제. |
| `governance/proposals/README.md` | → `context-directives` 선행 읽기 목록에 포함. 파일 삭제. |
| `telemetry/positions/README.md` | → `context-risk` 선행 읽기 목록에 포함. 파일 유지 (store contract SSoT). |

---

## 4. 기존 Skill 재구성 (S3)

### 현황

| Skill | 현재 줄수 | 상태 |
|---|---|---|
| `stage4-thesis-auditor/SKILL.md` | ~250 | 🔴 100줄 초과 — `domain/`(3파일) 이미 활용 중이나 본문 과다 |
| `stage6-brief-author/SKILL.md` | ~245 | 🔴 100줄 초과 — `domain/` 존재하나 비어 있음 |
| `stage0-regime-labeler/SKILL.md` | ~80 | 🟡 추정 (확인 필요) |
| `stage2-quality-lens/SKILL.md` | ~80 | 🟡 추정 |
| `audit-outcome/SKILL.md` | ~60 | 🟢 추정 |
| `audit-process/SKILL.md` | ~60 | 🟢 추정 |
| `ingest-external-signal/SKILL.md` | ~50 | 🟢 추정 |
| `policy-profiler/SKILL.md` | ~80 | 🟡 추정 |
| `contract/bootstrap.md` | ~260 | 🔴 skill 아님(shared contract). 100줄 하드캡 적용 제외하나, 가능한 범위 내 축소 검토. |

### 재구성 전략 (stage4-thesis-auditor 예시)

**현재 구조 (250줄)**:
- Reference Contract (15줄)
- Source of Truth Hierarchy (14줄)
- Required Identifier (16줄)
- Artifact Discovery table (17줄)
- 처리 절차 per ticker (30줄)
- Output Artifact (13줄)
- Output Mode A/B/C (45줄)
- Hard Guards table (21줄)
- Self-Validation checklist (17줄)
- Out of Scope (9줄)

**재구성 후 구조 (~80줄)**:
- SKILL.md: overview + 선행 읽기 목록 + 처리 흐름 6단계 + output 경로 + out of scope
- `domain/thesis-fields-format.md` (기존 유지)
- `domain/falsifier-validation.md` (기존 유지)
- `domain/edge-source-classification.md` (기존 유지)
- `domain/output-modes.md` (신규 — Mode A/B/C 상세)
- `domain/hard-guards.md` (신규 — G-mapping table)
- `domain/self-validation.md` (신규 — 12-step checklist)

---

## 5. Root AGENTS.md → Skill Index (~180줄)

```
# Agent Context: Retail Investment Pipeline

> Project Rules. 작업 전 해당 Context Skill invoke 필수.

## Quick Reference

| 하려는 작업 | invoke |
|---|---|
| `domains/screener/` 코드 | `/context-screener` |
| `domains/universe/` 코드 | `/context-universe` |
| ... (7 BC + directives + pipeline skills) | ... |

## Default = No Action

## 5대 철학 (1줄씩)

## Hard Guards (1~2줄씩 축약)

## 경로 해석 (표)

## 주요 디렉토리 (표)

## Forbidden Language
```

---

## 6. `investment-` prefix 제거 (S4)

| 대상 | 작업 |
|---|---|
| 9개 skill 디렉토리 rename | `git mv .agents/skills/investment-{name} .agents/skills/{name}` |
| 9개 SKILL.md frontmatter `name:` | `investment-` 제거 |
| `bootstrap.md` 내 skill 참조 | `$SKILLS_DIR/investment-*` → `$SKILLS_DIR/*` |
| `AGENTS.md` 내 skill 참조 | `/investment-*` → `/*` |
| `run_daily_local.sh` skill invoke | `/investment-stage4-thesis-auditor` → `/stage4-thesis-auditor` |
| `infrastructure/llm/dispatcher.py` | skill name reference 갱신 |

---

## 7. Skill 레지스트리 (목표 상태, prefix 제거 후)

### Context (8종 신규)

| # | Name | 줄수 |
|---|---|---|
| C0 | `context-directives` | ~80 |
| C1~C7 | `context-{macro,universe,screener,catalyst,risk,policy,audit}` | 각 ~60 |

### Pipeline (4종, 재구성)

| # | Name | 현재→목표 |
|---|---|---|
| P0 | `stage0-regime-labeler` | ~80→~60 |
| P2 | `stage2-quality-lens` | ~80→~60 |
| P4 | `stage4-thesis-auditor` | ~250→~80 |
| P6 | `stage6-brief-author` | ~245→~80 |

### Operational (4종)

| # | Name | 상태 |
|---|---|---|
| O1 | `audit-process` | ~60 유지 |
| O2 | `audit-outcome` | ~60 유지 |
| O3 | `ingest-external-signal` | ~50 유지 |
| O4 | `policy-profiler` | ~80→~60 |

### Shared (1종)

| # | Name | 비고 |
|---|---|---|
| X1 | `contract/bootstrap.md` | 100줄 하드캡 제외(shared contract). 가능한 축소 검토. |

---

## 8. 로드맵

```
Phase 0 (P0 — immediate)
├── S4: investment- prefix 전역 제거 (git mv 9 dirs + cross-ref)
├── S3a: stage4-thesis-auditor + stage6-brief-author 재구성 (250→80줄)
└── S2: Root AGENTS.md → Skill Index

Phase 1 (P0)
├── S1: Context Skills 8종 작성 (100줄 이내)
├── S3b: 나머지 7종 skill 재구성 + README 파일 흡수
└── README.md 정리 (capabilities/·decisions/·proposals/ 삭제)

Phase 2 (P1)
└── S5: Pre-commit + ruff + citation validator

Phase 3 (P2~P3)
├── S6: Output Validation Gate
├── S7: Runtime Invariant Monitor
└── S8: Vendor Capability Abstraction
```

---

## 9. 성공 기준

| 기준 | 측정 |
|---|---|
| 모든 SKILL.md ≤ 100줄 | `find .agents/skills -name "SKILL.md" -exec wc -l {} \;` → max ≤ 100 |
| `investment-` prefix 0건 | `grep -r "investment-" .agents/skills/` → 0 |
| `README.md` 0건 (root 제외) | `find . -name "README.md" \| grep -v "^\./README.md"` → 0 |
| Context Skills 8종 존재 + Root AGENTS.md에서 링크 | 디렉토리 + grep 확인 |
| 모든 보완 수단 vendor-free | `grep -r "anthropic\|claude -p" --include="*.py" --include="*.sh"` → `infrastructure/llm/` 외 0 |

---

## 10. 하지 않는 것 + Deferred

- `investment-` prefix 복원 — 전면 제거 확정
- 분산형 AGENTS.md 유지 — Skill로 전량 흡수
- `.guidelines/` 삭제 — Context Skill이 참조하는 reference로 존치
- `pre_env_guard` — Deferred
- `contract/bootstrap.md` 100줄 강제 — shared contract로 예외. 단, 축소 검토.
