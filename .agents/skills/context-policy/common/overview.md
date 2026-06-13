# policy — Enrich-Cutoff Profile Producer BC (out-of-band, Absorbed)

종목별 **Enrich-Cutoff profile** (required_enrichments + cutoff_rules) 를 trigger → research → commit 으로 생산하는 bounded context. universe/screener 의 daily batch 와 **분리된 자체 일정** (launchd). 현재 **cutover 前 dormant** (F-21/Phase 6).

## 패키지 구조

```
domains/policy/
  _boundary.py          # 외부 의존 단일 게이트 (DART / profiles 경로 / drafts / env)
  ports/llm.py          # PolicyEngine Protocol — Wave 5 port 패턴의 레퍼런스 템플릿
  domain/
    research_result.py  # ResearchOutput (frozen)
    trigger.py          # Trigger (frozen)
    drift.py            # Drift + compute_drift
    commit_gate.py      # drift/version/provenance 결정론 산술 (순수 — clock 주입)
  application/
    intake.py           # events → Trigger (순수)
    analyze.py          # Trigger + engine → ResearchOutput (engine 주입)
    commit.py           # ResearchOutput → ProfileRegistry 신규 버전 (drift gate)
  audit/                # citation + violation log
  main.py               # CLI — engine 미주입(기본)=intake-only / 주입 시 analyze+commit
```

## PolicyEngine Protocol (Wave 5 port reference)

```python
class PolicyEngine(Protocol):
    def analyze(self, trigger: Trigger, *, evidence: tuple[str, ...]) -> ResearchOutput: ...
```

`main(argv, *, engine: PolicyEngine | None = None)` 이 composition root 로 LLM 구현 주입. production research 는 `investment-policy-profiler` skill (phase 2).

## 3-phase 산출 flow (Phase 6a / F-10)

```
phase 1 (결정론)  python -m domains.policy.main --ticker T --trigger ...
                  → _emit_intake: _intake-{date}.json
phase 2 (LLM)     /policy-profiler T
                  → _intake + config/signals evidence → _profile-draft-{date}.json
phase 3 (결정론)  python -m domains.policy.main --commit-draft <draft>
                  → _commit_from_draft: validate_rules + decide_commit + G20
```

**스킬은 commit 안 함** — drift/version 산술은 `commit_gate.py` 결정론 (ADR-0003).

## 4 Anchor

1. **profile_registry 단일 source** — `_shared.profile_registry.registry.ProfileRegistry`
2. **commit-gate 단일 결정 경로** — `domain/commit_gate.decide_commit`
3. **drift detector 단일 source** — `domain/drift.compute_drift`
4. **`_boundary` 게이트** — 단일 infra-import ACL

## 외부 연결점

| 방향 | 인터페이스 | 게이트 |
|---|---|---|
| 입력 (trigger) | DART 공시 / CLI manual / news | `_boundary.dart_iter_disclosures` + `intake.build_triggers` |
| 입력 (LLM research) | trigger + evidence → ResearchOutput | `PolicyEngine` (ports/llm.py) — 주입 |
| 입력 (env) | `DART_API_KEY` | `_boundary.load_env` |
| 출력 (profile) | `governance/policy/profiles/{ticker}/` 신규 버전 | `_boundary.write_profile_safely` → `ProfileRegistry` |
| 출력 (draft) | `telemetry/policy_drafts/` (ephemeral) | `_boundary.drafts_dir` |

## CLI

`python -m domains.policy.main`: `--ticker` / `--trigger` / `--date` / `--drift-threshold` (0.5) / `--dry-run` / `--commit-draft`. exit 0 = 무트리거/intake/commit 성공. exit 2 = draft 부재/schema 오류/`ProfileDriftError`.

## Cutover 상태 (dormant)

- `governance/policy/profiles/` 비어있음 (`.gitkeep` 만)
- universe `--use-profile-registry` default OFF
- `DRIFT_BLOCKS_COMMIT = False` (advisory)

따라서 universe/screener 는 default 경로 → 일배치 동작 불변.
