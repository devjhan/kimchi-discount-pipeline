# domains/policy — Enrich-Cutoff Profile Producer BC (out-of-band)

종목별 **Enrich-Cutoff profile** (required_enrichments + cutoff_rules) 를 trigger →
research → commit 으로 생산하는 bounded context. universe/screener 의 daily batch 와
**분리된 자체 일정**으로 돌며 (launchd), consumer 는 `ProfileRegistry` 만 read 한다 —
policy 를 동기 호출하지 않는다. 현재 휴면 (cutover 전 — F-21/Phase 6).

## 패키지 구조

```
domains/policy/
  _boundary.py          # 외부 의존 단일 게이트 (DART / profiles 경로 / drafts / env)
  ports/llm.py          # PolicyEngine Protocol — **Wave 5 port 패턴의 레퍼런스 템플릿**
  domain/
    research_result.py  # ResearchOutput (frozen)
    trigger.py          # Trigger (frozen)
    commit_gate.py      # drift/version/provenance 결정론 산술 (순수 — clock 주입)
  application/
    intake.py           # events → Trigger (순수)
    analyze.py          # Trigger + engine → ResearchOutput (engine 주입)
    commit.py           # ResearchOutput → ProfileRegistry 신규 버전 (drift gate)
  audit/                # citation + violation log
  main.py               # CLI — engine 미주입(기본)=intake-only / 주입 시 analyze+commit
```

## Ports & Adapters (레퍼런스 템플릿)

**`ports/llm.py` 의 `PolicyEngine` Protocol** 이 Wave 5 전체 port 패턴의 원형이다 —
`main(argv, *, engine: PolicyEngine | None = None)` 이 composition root 로 LLM 구현을
주입하고, `application/analyze.run_analysis(trigger, engine, ...)` 은 Protocol 에만
의존한다 (LLM 교체/테스트 stub 자유). 구현(Zed skill / API)은 `_boundary` 뒤 — 단,
**스킬은 commit 안 함**: drift/버전 산술은 `commit_gate.py` 결정론 잔류 (F-10 불변식 —
[ADR-0003](../../governance/decisions/0003-llm-drafts-python-commits.md)).

> 본 BC 가 feature-first hexagonal 의 선례 (cross-cutting 일반화는 F-13 LLM port →
> D-CORE-7, 그리고 Wave 5 의 Citation/Disclosure/KisAccount port —
> [ADR-0005](../../governance/decisions/0005-boundary-ports-and-adapters.md)).

## 3-phase 산출 flow (Phase 6a / F-10 — 스킬 배선 완료)

production 의 LLM research 는 **`investment-policy-profiler` 스킬**(stage4 패턴)이 수행하며
3-phase 로 분리된다 — **스킬은 commit 안 함** (LLM→결정론 회수 교훈):

```
phase 1 (결정론)  python -m domains.policy.main --ticker T --trigger ...
                  → _emit_intake: _intake-{date}.json (trigger + 현 profile 동봉, G10 redacted evidence 힌트)
phase 2 (LLM)     /investment-policy-profiler T
                  → _intake + config/signals evidence → _profile-draft-{date}.json (ResearchOutput shape)
phase 3 (결정론)  python -m domains.policy.main --commit-draft <draft>
                  → _commit_from_draft: validate_rules(shape) + decide_commit(drift/version/provenance) + G20
```

2 결정론 가드: ① intake redaction (G10 — `build_triggers` 가 payload_ref 만, raw 미보관)
② commit `validate_rules` (cutoff_rules shape; 전체 합법성은 screener 로드 시 caution 격리).
**PolicyEngine Protocol 은 존속** — 테스트 stub seam + 프로그램적 engine 주입 경로(`main(engine=...)`).

> **cutover (6b~6e) 미실행 / F-21 open.** universe `--use-profile-registry` 기본 OFF +
> `governance/profiles/` 빈 상태라 universe/screener 는 여전히 default 경로 — daily 동작 불변.
> 활성화는 1주 dry-run diff 후 사용자 결정.

## 외부 연결점

| 방향 | 인터페이스 | 게이트 |
|---|---|---|
| 입력 (trigger) | DART 공시 (filing trigger) / CLI manual / news | `_boundary.dart_iter_disclosures` + `intake.build_triggers` |
| 입력 (LLM research) | trigger + evidence → ResearchOutput | `PolicyEngine` (ports/llm.py) — 주입 |
| 입력 (env) | `DART_API_KEY` | `_boundary.load_env` |
| 출력 (profile) | `governance/profiles/{ticker}/` 신규 버전 | `_boundary.write_profile_safely` → `ProfileRegistry` |
| 출력 (draft) | `telemetry/policy_drafts/` (commit 전 ephemeral) | `_boundary.drafts_dir` |

## 검증

```bash
grep -rn "from infrastructure\|import infrastructure" domains/policy/ --include="*.py" | grep -v _boundary.py   # → 0
# 불변식: 스킬(LLM)은 commit 안 함 — drift/version 은 commit_gate.py 결정론
```
