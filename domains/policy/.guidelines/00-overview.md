# policy — DDD Modular Monolith Overview

종목별 **Enrich-Cutoff Profile** 의 out-of-band **producer** BC. per-ticker
`EnrichCutoffProfile` (= `required_enrichments` (universe 가 적용할 enricher) +
`cutoff_rules` (screener Rule dict-tree)) 를 `trigger → research → commit` 흐름으로 생산한다.
자체 schedule (launchd) 로 universe/screener 일배치와 **decouple** 되어 돌며, consumer 는
committed profile 을 `ProfileRegistry` 로 *읽기*만 하고 policy 를 동기 호출하지 않는다.
committed SSoT 는 `governance/profiles/{ticker_dir}/v{N}.yaml`. 현재 **cutover 前 dormant**
(F-21 / Phase 6).

> 용어 구분: `domains/policy/` 는 정책을 *author*; `domains/_shared/profile_registry/` 는
> artifact 의 *contract/storage*; `governance/profiles/` 는 on-disk SSoT.

## ADR-0003 구현 (LLM drafts, Python commits)

코드가 **3-phase split** 으로 LLM 에게서 commit 권한을 박탈한다:
- **phase 2** (`investment-policy-profiler` skill = `PolicyEngine` 구현) 은 `ResearchOutput`
  *draft* 만 생산.
- **모든 결정론 산술** — version 발급 (`next_version`), drift 계산 (`compute_drift`),
  drift ruling (`rule_on_drift`), provenance 조립 (`assemble_profile`), 통합 `decide_commit` —
  은 pure Python `domain/commit_gate.py`.
- **commit** (`application/commit.commit_profile` → `ProfileRegistry.commit`) 도 결정론 Python.

불변식: **스킬은 commit 안 함** (ADR-0003 / `governance/decisions/0003-llm-drafts-python-commits.md`).

## 4 Anchor (변경 시 도메인 안정성 영향)

1. **profile_registry 단일 source** — `domains._shared.profile_registry.registry.ProfileRegistry`
   (read: `load_latest`/`load_version`/`list_versions`; write: `commit`). committed profile 의
   유일 read/write 경로.
2. **commit-gate 단일 결정 경로** — `domain/commit_gate.decide_commit` (orchestration
   `application/commit.commit_profile`). version 발급 + drift ruling + profile 조립이 여기로 funnel.
3. **drift detector 단일 source** — `domain/drift.compute_drift` (policy 소유 — screener rule-tree
   지식 필요해 `_shared` 미이전, rule-of-three 미충족).
4. **`_boundary` 게이트** — `domains.policy._boundary` (단일 infra-import ACL).

(보조 anchor: `domain/commit_gate.DRIFT_BLOCKS_COMMIT` — warn↔block 단일 토글, 현재 `False`.)

## 패키지 핵심 객체 (frozen dataclass)

### domain/
- `trigger.py` `Trigger` — `kind` / `ticker` / `payload_ref` / `detected_at` (**ref 만, raw payload 미보유** — G10)
- `research_result.py` `ResearchOutput` — `ticker` / `required_enrichments` / `cutoff_rules` /
  `citations` / `rationale_ko` (pre-commit candidate, PolicyEngine 산출)
- `drift.py` `Drift` (`enrichments_added/removed` / `changed_thresholds` / `max_threshold_delta`) + `compute_drift`
- `commit_gate.py` `DriftRuling` / `CommitDecision` + 결정론 규칙 (`next_version` / `rule_on_drift` /
  `assemble_profile` / `decide_commit`) + `DRIFT_BLOCKS_COMMIT`

### ports/
- `llm.py` `PolicyEngine` (Protocol) — `analyze(trigger, *, evidence) -> ResearchOutput` (Wave-5 port reference template)

### application/
- `intake.py` `build_triggers` — events → Trigger (pure)
- `analyze.py` `run_analysis` — `engine.analyze` 위임 (Protocol 의존)
- `commit.py` `CommitResult` + `commit_profile` + `shape_validate_cutoff_rules`

### audit/
- `log.py` `ViolationLog` (bc_name="policy") / `violation.py` / `citation.py` — `_shared` shim

### main.py — CLI entry (`python -m domains.policy.main`)
- `--ticker` / `--trigger` / `--date` / `--drift-threshold` (0.5) / `--dry-run` / `--commit-draft`
- 프로그램 seam: `main(argv=None, *, engine: PolicyEngine | None = None) -> int`

## 산출 / 외부 연결점

- **committed profile (SSoT)**: `governance/profiles/{ticker_dir}/v{N}.yaml`
  (`_boundary.write_profile_safely` → `ProfileRegistry.commit`, G20). `ticker_dir` = `":" → "_"`.
- **ephemeral draft**: `telemetry/policy_drafts/{ticker_dir}/_intake-{date}.json` (phase1) +
  `_profile-draft-{date}.json` (phase2 산출, `write_output_safely`). gitignore.
- **audit JSONL**: `$AUDIT_DIR/policy-violations/{date}.jsonl`
- schema 문자열: `SCHEMA_VERSION = "enrich-cutoff-profile-v1"`; `STAGE_NAME = "policy-producer"`
- handoff (stdout, 예): `[policy-producer] committed {ticker} v{version} (drift Δ{...}) → {path}`
  / 무트리거 시 `[policy-producer] no triggers — Default No-Action`

## exit

- `0` = 무트리거(Default No-Action) / intake-only emit / commit 성공(blocking 없음)
- `2` = draft path 부재 / 불량 draft schema / `ProfileDriftError` (hard-block) / `audit_log.has_blocking`
