# Commit Governance — draft → drift → commit

## 3-phase 흐름

### phase 1 — intake / draft (LLM·commit-free, G10)
- `_emit_intake(triggers, clock)` (`main.py`) — ticker 별 `_intake-{date}.json` 작성
  (trigger + 현 profile 요약 + `evidence_dir_hint = config/signals/{ticker_dir}/`).
- `build_triggers(events, *, now_iso) -> tuple[Trigger, ...]` (`application/intake.py`) — pure;
  불완전 event silent skip; `payload_ref` 만 보존 (G10 — raw payload 미보유).

### phase 2 — research (engine, 결정론 코드 아님)
- `run_analysis(trigger, engine, *, evidence=()) -> ResearchOutput` (`application/analyze.py`).
  skill 이 intake + `config/signals/{ticker_dir}/` evidence → `_profile-draft-{date}.json` 작성.

### phase 3 — drift + commit (결정론)
- `_commit_from_draft(path, clock, *, drift_threshold)` (`main.py`) — draft JSON 로드
  (`raw.get("payload", raw)`) → `ResearchOutput` 재구성 → `commit_profile`.
- `commit_profile(out, registry, *, writer, audit_log, drift_threshold, validate_rules=
  shape_validate_cutoff_rules, trigger="manual") -> CommitResult` (`application/commit.py`) —
  shape validate → `registry.load_latest(prev)` → `decide_commit(...)` → (threshold 초과 시) audit →
  `registry.commit`.
- `shape_validate_cutoff_rules(cutoff_rules)` — shape-only (`Mapping` + `"type"` 키, else `ValueError`).
  full rule 합법성은 screener 권한.

pure 규칙 (`domain/commit_gate.py`):
```python
next_version(prev) -> int                  # (prev.profile_version + 1) if prev else 1
rule_on_drift(prev, out, *, drift_threshold) -> DriftRuling
assemble_profile(out, *, version, committed_at, trigger) -> EnrichCutoffProfile   # committed_by="policy"
decide_commit(prev, out, *, drift_threshold, committed_at, trigger) -> CommitDecision
```

## drift 탐지 (`domain/drift.compute_drift`)

```python
compute_drift(prev: EnrichCutoffProfile | None, new_required, new_cutoff_rules) -> Drift
```
- `prev is None` → `Drift((), (), {}, 0.0)` (초기 commit, drift 없음).
- enrichment set diff → `enrichments_added` / `enrichments_removed` (sorted).
- threshold-node diff: `_collect_thresholds` 가 rule dict-tree 재귀 walk (`type=="threshold"` 노드의
  `{name: threshold}` 수집; `children`/`inner` + `weighted_sum {"rule":..,"weight":..}` 처리).
  screener `factory._collect_rule_names` 와 의도적 isomorphic (screener 내부 import 대신 재구현 —
  도메인 경계 보존).
- `max_threshold_delta = max(|new-old|/|old|)` (공유 rule, `old != 0`).

`exceeds_threshold` = `bool(prev) and drift.max_threshold_delta > drift_threshold`.

## DRIFT_BLOCKS_COMMIT (warn ↔ block 단일 토글)

`domain/commit_gate.py` 의 **모듈 상수** `DRIFT_BLOCKS_COMMIT = False` (env/CLI 아님).
`DriftRuling.blocks_commit = exceeds_threshold and DRIFT_BLOCKS_COMMIT`.
`commit_profile` 에서 `ruling.exceeds_threshold` 시:
- audit `GuardViolation` 기록 — `severity = "blocking" if blocks_commit else "warning"`
- `blocks_commit` True 면 `ProfileDriftError(f"{ticker} drift Δ{...} > {drift_threshold} (hard block)")` raise

현재 `False` → **advisory mode**: over-threshold drift 는 warning audit 만 남기고 commit 진행.
`--drift-threshold` (default 0.5) 는 *언제* 초과인지, `DRIFT_BLOCKS_COMMIT` 는 *초과가 막는지* 를 제어.

## telemetry/policy_drafts/ lifecycle

gitignore, 현재 비어있음. `_boundary.drafts_dir()` (= `policy_drafts_dir()`):
1. phase1 → `{ticker_dir}/_intake-{date}.json` (trigger + 현 profile 요약 + evidence hint)
2. phase2 (skill) → intake + `config/signals/{ticker_dir}/` evidence 읽어 `_profile-draft-{date}.json`
3. phase3 → `--commit-draft <path>` 로 draft 읽어 promotion

둘 다 `write_output_safely` (JSON, G20). draft 는 pre-commit candidate; durable artifact 는
committed `governance/profiles/.../v{N}.yaml`.

## cutover 상태 (dormant)

BC 는 **cutover 前 dormant (F-21 / Phase 6)**. Phase 6a/F-10 (skill wiring) 은 done (2026-06-06).
6b~6e 잔여 — **1주 dry-run diff + user 결정 gated**. 미flip 3종:
1. `governance/profiles/` 비어있음 (`.gitkeep` 만)
2. universe `--use-profile-registry` default OFF
3. `DRIFT_BLOCKS_COMMIT = False` (advisory)

따라서 universe/screener 는 여전히 default 경로 → 일배치 동작 불변. cutover (PR7) 시
`DRIFT_BLOCKS_COMMIT` flip 으로 blocking 확정 (`commit_gate.py` docstring).
