---
name: policy-profiler
description: Investment 파이프라인의 out-of-band Policy Producer 의 LLM research 단계 (Phase 6a / F-10). domains.policy 의 trigger 별 _intake (trigger + 현 profile + evidence) 를 읽어 종목별 Enrich-Cutoff profile 후보 (required_enrichments + cutoff_rules + citations + rationale_ko) 를 _profile-draft-{date}.json 으로 산출한다. **스킬은 commit 하지 않는다** — drift/version/provenance/G20 은 'python -m domains.policy.main --commit-draft <draft>' 결정론이 소유 (스킬은 환각 차단을 위해 draft 만). cutoff_rules 는 screener RuleFactory 소비 가능 문법만 (resolver whitelist 밖 metric_path 금지). 정량 계산 / 사이즈 / drift 산술 일체 금지.
---

# policy-profiler — Enrich-Cutoff Profile Research (out-of-band)

`domains/policy`의 **LLM research 단계** (Phase 2). 3-phase 중 phase 2 만 수행하며,
commit/drift/version/provenance 산술은 절대 하지 않는다 (F-10).

```
phase 1 (결정론)  python -m domains.policy.main --ticker T --trigger ...  → _intake-{date}.json
phase 2 (LLM=본 스킬)  _intake + evidence → _profile-draft-{date}.json
phase 3 (결정론)  python -m domains.policy.main --commit-draft <draft>    → ProfileRegistry 신규 버전
```

## 선행 읽기

### 공통
1. `common/cutoff-rules-grammar.md` — methods_manifest 화이트리스트 + Rule 문법
2. `common/hard-guards.md` — F-10 / G6/G7/G10/G11/G20/G21 가드
3. `common/self-validation.md` — 9-step 체크리스트

### 분기
- `mode-write/output.md` — Mode A: draft 작성 조건·절차
- `mode-needs-user/output.md` — Mode B: 사용자 확인 필요 조건·응답
- `mode-block/output.md` — Mode C: 차단 조건·응답

## Required Identifier

`ticker: KR:NNNNNN (필수)` / `date: YYYY-MM-DD (KST). 미지정 시 오늘`

## 핵심 불변식

1. **LLM draft only (F-10)** — commit/drift/version/provenance/registry write 절대 금지. 결정론 `--commit-draft`만 수행
2. **cutoff_rules 화이트리스트** — `metric_path`는 `methods_manifest.yaml` 내 resolver 소비 가능 경로만
3. **evidence 없는 임계값 금지 (G7)** — 모든 수치 임계에 `{SOURCE}@{ts}={value}` citation 강제

## 처리 흐름 (per ticker, 7-step)

1. `_intake-{date}.json` read → trigger + current_profile
2. `$EXTERNAL_SIGNAL_INTAKE_DIR/{ticker_dir}/*.md` evidence read
3. `required_enrichments` 제안 / `cutoff_rules` 제안
4. citations / `rationale_ko` 작성
5. `_profile-draft-{date}.json` write (기존 파일 시 `.{N}.json` — G20)

## 산출물

- `$POLICY_DRAFTS_DIR/{ticker_dir}/_profile-draft-{date}.json`
- 후속: `python -m domains.policy.main --commit-draft <draft>` (phase 3)

## Out of Scope

- commit/drift/version/provenance (phase 3 `--commit-draft` 결정론) / ProfileRegistry write / universe/screener batch 호출 / trigger 발견·DART scan (phase 1) / 사이즈·Kelly·매매·알림 (G6/G9)
