---
name: context-policy
description: domains/policy/ (Enrich-Cutoff) 코드 읽기/수정 전 반드시 로드. 미로드 시 profile producer·enrichment·cutoff·RuleFactory whitelist 불변식 위반 확정. common/ 통합 가이드 선행 읽기 안내 포함.
---

# context-policy

`domains/policy/` BC (Enrich-Cutoff Profile Producer, out-of-band) 코드 작업 전 invoke. 본문은 인덱스 — 상세는 `common/` 파일 참조.

## 선행 읽기

### 공통 (common/)
1. `common/overview.md` — BC 개요, 패키지 구조, 3-phase flow, PolicyEngine Protocol (Wave 5 port template), 외부 연결점 테이블, cutover 상태 (dormant), 4 Anchor
2. `common/profile-engine.md` — PolicyEngine Protocol (ports/llm.py), EnrichCutoffProfile schema (ADR-0006 fat contract), ProfileRegistry API, governance/policy/profiles/ 포맷
3. `common/commit-governance.md` — 3-phase 분리 (intake → research → commit), drift 탐지 (compute_drift), DRIFT_BLOCKS_COMMIT toggle, commit gate pure 규칙
4. `common/boundaries.md` — `_boundary.py` 게이트, invariant-C/D GREEN, draft JSON vs commit YAML writer 구분, DART API
5. `common/audit.md` — ViolationLog (profile_drift rule_name), G-guard 적용표, ADR-0003 구조적 enforcement
6. `common/config-contract.md` — Tunable CLI flag, committed artifact schema, D-CFG-1, schema bump 규약

## 핵심 불변식

- **3-phase flow**: phase 1 (결정론 intake) → phase 2 (LLM draft, skill `policy-profiler`) → phase 3 (결정론 commit, `--commit-draft`)
- **스킬은 commit 안 함 (F-10)**: LLM skill 은 `_profile-draft-{date}.json` 까지만 산출 — drift/version/provenance 산술은 `commit_gate.py` 결정론이 독점
- **`cutoff_rules` = screener `RuleFactory` 소비 가능 문법만**: `methods_manifest` 화이트리스트 밖 `metric_path` 금지, screener resolver 가 해석 불가능한 rule shape → commit 시 `validate_rules` reject
- **`PolicyEngine` Protocol**: LLM 구현을 주입받는 seam — 테스트 stub + vendor 교체 경로 보존

## 전형적 실패 패턴

- LLM 이 직접 commit: skill 이 `_profile-draft` 를 넘어 `ProfileRegistry` 에 직접 write → F-10 위반, 결정론 회수 실패
- `metric_path` 화이트리스트 밖: `cutoff_rules` 에 screener `methods_manifest` 미등록 metric 경로 사용 → screener 로드 시 `caution` 격리
- Evidence 없는 임계값 지어내기: LLM 이 구체적 evidence citation 없이 cutoff threshold 수치를 생성 → G7/G8 위반 (hallucination 최고 severity)
- Cutover 오해: `--use-profile-registry` 기본 OFF (F-21 open), `governance/policy/profiles/` 빈 상태 → universe/screener 는 default 경로로 동작 중

## 산출물

- `$POLICY_DRAFTS_DIR/{ticker}/_intake-{date}.json` — phase 1 intake (trigger + 현 profile + redacted evidence)
- `$POLICY_DRAFTS_DIR/{ticker}/_profile-draft-{date}.json` — phase 2 LLM draft (`ResearchOutput` shape)
- `governance/policy/profiles/{ticker}/` — phase 3 committed profile (결정론 gate 통과 후)

## Out of Scope

- 다른 BC 의 책임 — screener / universe / catalyst 내부 import 금지
- Profile 의 실제 소비 (screener 가 `ProfileRegistry` read) — consumer 측 책임
- LLM research 수행 — skill `policy-profiler` 책임 (본 BC 는 intake + commit gate 만)
