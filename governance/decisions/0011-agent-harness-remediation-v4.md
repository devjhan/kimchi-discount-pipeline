# ADR-0011 — Agent Harness Remediation v4: Skill-First Context Injection + 100줄 하드캡

`status: Accepted`
`date: 2026-06-11`
`refs: G1-G22, D-ARCH-6, ADR-0009, ADR-0010`

## Context

ADR-0009 (Claude Code → Zed Agent Migration) 이후 잔여 gap: Claude Code의 분산형 AGENTS.md 패턴을 Zed 1.6.3 "Rules to Skills migration"(#58278)에 정렬해야 한다. 기존 9종 skill은 `investment-` prefix를 가지며, 일부 SKILL.md가 250줄을 초과해 단일 파일로 과다하다. 또한 BC별 작업 시 domain context를 주입할 mechanism이 부재하다.

## Decision

다음 7개 축의 보완을 실행한다:

1. **Skill-First Context Injection**: Root `AGENTS.md`를 Skill Index로 전환하고, 8종 Context Skill을 신설해 BC별 domain context를 주입한다.
2. **100줄 하드캡 + `common/`·`mode-{}/` 구조**: 모든 SKILL.md를 100줄 이내 index로 재작성. 상세는 `common/`(공통) + `mode-{name}/`(분기별) 서브디렉토리로 분산.
3. **`investment-` prefix 제거**: 9개 skill 디렉토리 rename + 모든 cross-reference 갱신. Layer prefix만 유지 (`context-`, `stage{N}`, `audit-`, `ingest-`, `policy-`).
4. **`.guidelines/` + BC `AGENTS.md` 흡수**: 7개 BC의 AGENTS.md와 42개 .guidelines/ 파일 전체를 `context-{bc}/common/`으로 물리 병합 후 원본 삭제.
5. **README 흡수**: `governance/capabilities/`, `governance/decisions/`, `governance/proposals/`의 README.md를 `context-directives` skill 선행 읽기로 흡수 후 삭제.
6. **`governance/directives/AGENTS.md` 흡수**: D-ID 매핑 인덱스를 `context-directives/SKILL.md`에 인라인. 실제 directive `.md` 파일은 존치.
7. **결정론 도구 분리 우선**: Pre-commit/S6/S7/S8은 Phase 2~3으로 deferred.

## Consequences

### 강제하는 것

- 모든 SKILL.md ≤ 100줄, SKILL.md는 index 역할만
- 모든 skill 내부: `common/`(공통 지식) + `mode-{name}/`(분기별 output 조건·절차)
- BC 작업 시 해당 `/context-{bc}` skill invoke가 표준 절차
- `investment-` prefix 완전 제거 — 신규 skill은 `{layer}-{role}` 컨벤션
- Root `AGENTS.md`는 인덱스 역할만 — 상세는 각 skill이 소유
- 더 이상 BC별 `AGENTS.md`·`.guidelines/` 없음 — skill이 SSoT

### 포기하는 것

- Claude Code 분산형 AGENTS.md + .guidelines/ 패턴 — Zed skill-first 모델로 전환
- BC AGENTS.md (도메인 수준 인덱스) — context skill common/으로 대체
- README.md 중앙 인덱스 — skill 선행 읽기로 흡수

### 후속 영향

- 신규 BC 추가 시 `/context-{bc}` skill 동시 생성 + common/ 기본 구조 확립
- `capabilities/*.md` 개별 파일은 존치 (C1~C6 각 capability 문서는 skill이 참조)
- `decisions/*.md` ADR 본문은 존치 (append-only ledger)
- `governance/directives/00-principles.md` 등 `.md` 파일은 존치 (governance artifact, fitness test  참조)

## Alternatives considered

- **분산형 AGENTS.md 유지**: Claude Code 패턴을 Zed에서 재현하려 했으나, Zed의 agent skill model이 더 적합. 기각.
- **investment- prefix 복원**: Layer 구분만으로 충분하며, prefix는 중복. 기각.
- **context-stage0 skill 신설**: Stage 0는 LLM narrative labeler가 담당 — pipeline skill로 충분. 기각.
- **contract/bootstrap.md 100줄 강제**: Shared contract는 cross-cutting SSoT로 예외. 기각.
- **.guidelines/ 존치**: Skill common/으로 흡수 후 원본 제거가 더 단순한 컨텍스트 모델. 기각.

## Verification

```
find .agents/skills -name "SKILL.md" -exec wc -l {} \; → max 79 ≤ 100 ✅
grep -r "investment-" .agents/skills/ → 0 matches ✅
find . -name "README.md" | grep -v "^\./README.md" | grep -v "pytest_cache" | grep -v "positions" → 0 ✅
ls -d .agents/skills/*/ → 17 directories (Context 8 + Pipeline 4 + Operational 4 + Shared 1) ✅
# BC AGENTS.md + .guidelines/ 삭제 확인
find domains -name "AGENTS.md" -not -path "*venv*" -not -path "*.git*" → 0 ✅
find domains -name ".guidelines" -type d -not -path "*venv*" -not -path "*.git*" → 0 ✅
# 모든 skill에 common/ 또는 mode-{}/ 존재
find .agents/skills -mindepth 2 -type d -not -path "*/contract/*" | grep -E "common|mode-" | wc -l → ≥ 22 (8 pipeline-skill directories) ✅
```
