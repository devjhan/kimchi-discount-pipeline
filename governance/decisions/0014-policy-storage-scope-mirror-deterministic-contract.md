# ADR-0014 — 정책 저장소 scope-미러 재구조화 + 결정론적 policy contract (manifest + ruff + arch fitness)

`status: Accepted (구현 완료 — implemented 2026-06-14)`
`date: 2026-06-14`
`refs: 0012, 0013, 0010(hook-disposition), D-ARCH-1, D-CORE-5, domains/_shared/{policy_profile,profile_registry,segment_registry}, domains/screener/rules/, domains/policy/`

## Context

ADR-0013 은 정책 스키마를 단일 `policy-profile-v1`(scope ∈ {global, segment, ticker})로
통합했으나, *저장 레이아웃* 은 구 per-tier 디렉토리를 `governance/policy/` 밑으로
**평면 이동(lift-and-shift)** 만 했다. 결과적으로 스키마는 하나인데 디스크는 세 갈래의
"profiles" 개념이 서로 다른 깊이에 흩어졌다:

| 구 경로 | scope/kind | 문제 |
|---|---|---|
| `profiles/<TICKER>/` | profile, ticker | 이름이 "ticker"를 안 드러냄 |
| `segment_profiles/<name>/` | profile, segment | `segments/`(멤버십)와 형제처럼 보이나 *정책* |
| `global/profiles/<name>.yaml` | profile, global | 세 번째 "profiles", 중첩, flat·비-versioned |
| `global/{strategies,hard_guards}` | screener config | global *profile* 과 동거 |

추가로 7개의 incompleteness/inconsistency 가 식별됐다 (아래 "Findings").

## Decision

### 1. 저장 레이아웃이 스키마의 scope 축을 미러한다.
profile 은 단일 객체이고 유일한 분기축이 `scope` 이므로, 저장 위치도 그 축을 그대로 반영한다.

```
governance/policy/
├── profiles/
│   ├── global/<name>/v<N>.yaml        # scope=global   — precedence base
│   ├── segment/<name>/v<N>.yaml       # scope=segment  — segments[].profile_ref 대상
│   └── ticker/<KR_NNNNNN>/v<N>.yaml   # scope=ticker    — per-ticker override
├── segments/<id>/v<N>.yaml            # cohort 멤버십 (segment-def-v1)
├── concepts/<id>/v<N>.yaml            # semantic anchor (segment-concept-v1)
├── strategies/<name>/v<N>.yaml        # screener 조합 (screener-strategy-v1) — versioned
└── hard_guards.yaml                   # G13 catastrophic floor (singleton, flat)
```

- 구 `segment_profiles/` → `profiles/segment/` (= `segments` vs `segment_profiles` 혼동 + `named_profiles` vs `profiles` 혼동 동시 해소).
- 구 `global/` 해체: profile → `profiles/global/`, strategy → `strategies/`, hard_guards → top-level singleton.
- global·strategy 도 versioned-dir(`<name>/v<N>.yaml`)로 통일 (ADR-0013 이 명시했으나 미구현이던 "버저닝 단일화" 완성).
- 코드 정합: `NamedProfileRegistry → SegmentProfileRegistry`; path helper 를 scope-named 로
  (`ticker_profiles_dir`/`segment_profiles_dir`/`global_profiles_dir`/`strategies_dir`/`hard_guards_path`).

### 2. 결정론적 policy contract — 코드 SSoT manifest + arch fitness + ruff.
정책 검증을 문서가 아닌 **빌드 실패 게이트** 로 고정한다 (hook 부재 — ADR-0010; D-CORE-5 runtime zero-dep 준수, ruff 는 dev-only).

- **`governance/policy/methods_manifest.yaml`** — 코드 SSoT(screener `resolver`/`factory`/`leaf`
  + segment_registry `attributes`)에서 **생성** 되는 산출물. `metric_paths` / `enrichment_metric_paths`
  / `rule_types` / `threshold_ops` / `selection_attributes` / `selector_ops`. 생성기:
  `python -m applications.gen_methods_manifest`. `test_methods_manifest_sync` 가 코드↔파일 동기를 강제.
- **strict cutoff validator** (`domains/policy/domain/cutoff_validate.py`) — manifest 를 **DATA** 로
  읽어(bc-independence: policy 는 screener internal 을 import 안 함) cutoff_rules 의 type/metric_path/op
  를 검증. `domains.policy.main` composition root 가 `commit_profile(validate_rules=...)` 로 주입 →
  불량 profile 은 `--commit-draft` 시점에 결정론적으로 reject (구: screener 로드 시점 silent degrade).
- **arch fitness functions** (stdlib pytest, `@pytest.mark.arch`):
  - `test_policy_layout` — path↔scope 일치 + versioned-only + clean top-level.
  - `test_methods_manifest_sync` — manifest ↔ code 동기.
  - `test_policy_contract` — 전 정책 YAML serde 로드 + 참조 무결성(profile_ref/concept) + manifest 적합성.
  - `test_policy_consolidation` — 신규 tree 거주 + 구 레이아웃(global/·segment_profiles/) 금지.
- **ruff** (dev dep, `make lint`/`make check`) — Python lint 레이어 (F/E4/E7/E9/B, 점진 확대).

### 3. 엔진 결합은 불변 (ADR-0013 decision 3 유지).
cutoff *평가* 는 여전히 screener `RuleFactory` 소유. manifest/validator 는 *저작·저장* 검증일 뿐
엔진을 통합하지 않는다. golden parity(`test_screener_policy_profile_parity`)로 빌드된 Rule 트리가
재구조화 전과 byte-identical 임을 고정.

## Findings closed (deterministically)

| # | Finding | Gate |
|---|---|---|
| 1 | `methods_manifest.yaml` dangling ref | 생성 산출물 + sync test |
| 2 | grammar type-enum 부정확(scoring/weighted_sum 누락) | manifest `rule_types` (code SSoT) |
| 3 | selector `ne` vs cutoff op 불일치 silent | strict validator (commit 시점 reject) |
| 4 | global 비-versioned 비대칭 | `profiles/global/<name>/v<N>.yaml` + layout test |
| 5 | per-ticker 예시 부재 | LG `profiles/ticker/KR_003550/` (Phase 5) + contract test |
| 6 | `segments`/`segment_profiles` 혼동 | scope-미러 재구조화 (`profiles/segment/`) |
| 7 | drift 가 threshold 노드만 추적 | `_collect_thresholds` → scoring/weighted_sum pass_score |

## Consequences

- **인지부하↓** — "profile = `profiles/<scope>/<key>/v<N>.yaml`, scope 가 곧 경로". 단일 멘탈 모델 완성.
- **오배치 불가** — path↔scope 불변식이 빌드 게이트. 환각 metric_path/op·dangling ref 도 build red.
- **마이그레이션 비용** — path helper/boundary/registry 클래스명/arch test/문서 갱신 (1 PR). golden parity 로 행동 불변 증명.
- **env var 재명명** — `PROFILES_DIR`→`TICKER_PROFILES_DIR`, `GLOBAL_POLICY_DIR` 제거, 신규 `GLOBAL_PROFILES_DIR`/`STRATEGIES_DIR`/`POLICY_ROOT_DIR` (override 사용처 없음 — 기본 경로 변경만).
- **ruff dev-dep 추가** — runtime zero-dep(D-CORE-5) 불변; pytest/pytest-cov 와 동급 dev tool.

## Supersedes / Superseded-by

- **Extends/Amends** ADR-0013 — 저작/저장 *통합* 을 scope-미러 *재구조화* + 결정론 contract 로 완성.
  ADR-0013 의 "flat merge" 결과물(`global/`·`segment_profiles/`)을 대체. (append-only — 0013 은 historical.)
- **Extends** ADR-0010 — hook 부재 환경의 enforcement 를 arch fitness + ruff 로 구체화.
- Supersede 없음.
