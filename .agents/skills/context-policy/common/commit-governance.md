# Commit Governance — draft → drift → commit

## 3-phase 흐름

### phase 1 — intake / draft (LLM·commit-free, G10)
- `_emit_intake(triggers, clock)` — ticker 별 `_intake-{date}.json` (trigger + 현 profile 요약 + evidence hint)
- `build_triggers(events, *, now_iso) -> tuple[Trigger, ...]` — pure; payload_ref 만 보존 (G10)

### phase 2 — research (LLM skill, 결정론 코드 아님)
- `run_analysis(trigger, engine, *, evidence=()) -> ResearchOutput` → `_profile-draft-{date}.json`

### phase 3 — drift + commit (결정론)
- `_commit_from_draft(path, clock, *, drift_threshold)` → draft JSON 로드 → `commit_profile`
- `commit_profile(out, registry, *, writer, audit_log, drift_threshold, validate_rules=shape_validate_cutoff_rules)` → shape validate → `decide_commit` → `registry.commit`

## drift 탐지 (`domain/drift.compute_drift`)

```python
compute_drift(prev: EnrichCutoffProfile | None, new_required, new_cutoff_rules) -> Drift
```

- enrichment set diff → `enrichments_added` / `enrichments_removed` (sorted)
- threshold-node diff: rule dict-tree 재귀 walk → `max_threshold_delta`
- `exceeds_threshold = bool(prev) and drift.max_threshold_delta > drift_threshold`

## DRIFT_BLOCKS_COMMIT

`domain/commit_gate.py` 의 **모듈 상수** `DRIFT_BLOCKS_COMMIT = False`. 현재 **advisory mode** — over-threshold drift 는 warning audit 만 남기고 commit 진행. 향후 flip 으로 blocking 확정.

## telemetry/policy_drafts/ lifecycle

gitignore. phase1 → `{ticker_dir}/_intake-{date}.json`. phase2 (skill) → `_profile-draft-{date}.json`. phase3 → `--commit-draft <path>` 로 draft 읽어 promotion. 모두 `write_output_safely` (G20).

## Commit gate pure 규칙

```python
next_version(prev) -> int
rule_on_drift(prev, out, *, drift_threshold) -> DriftRuling
assemble_profile(out, *, version, committed_at, trigger) -> EnrichCutoffProfile
decide_commit(prev, out, *, drift_threshold, committed_at, trigger) -> CommitDecision
```
