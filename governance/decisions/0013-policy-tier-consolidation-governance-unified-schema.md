# ADR-0013 — 정책 계층 통합: 전 tier governance/ 단일화 + scope-tagged enrich-cutoff 스키마 통합 (per-ticker→segment 추상화 보류)

`status: Accepted (구현 완료 — implemented 2026-06-13)`
`date: 2026-06-13`
`refs: D-ARCH-1, D-ARCH-4, 0002, 0006, 0008, 0012, domains/_shared/profile_registry/, domains/_shared/segment_registry/, domains/screener/config/`

> **Amended by ADR-0014 (2026-06-14)**: 본 ADR 의 *flat-merge* 저장 결과(`governance/policy/{segment_profiles,global}/`)는 ADR-0014 에서 schema 의 scope 축을 미러하는 트리(`profiles/{global,segment,ticker}/`, `strategies/`, `hard_guards.yaml`)로 재구조화됨 + 코드 SSoT manifest·strict validator·arch fitness 로 결정론 contract 추가. 아래 본문의 경로 표기는 ADR-0013 시점 기준 (현행은 ADR-0014 참조).

## Context

정책(profile)이 **3 tier로 분산**되어 있다:

| tier | 저장 위치 | 로더 / 엔진 | 스키마 |
|---|---|---|---|
| per-ticker | `governance/profiles/<ticker>/v<N>.yaml` | `_shared/profile_registry` | `enrich-cutoff-profile-v1` |
| segment | `governance/segments|concepts|segment_profiles/` | `_shared/segment_registry` (ADR-0012) | `segment-profile-v1` 등 |
| whole-universe(global) | `domains/screener/config/{strategies,profiles,hard_guards}.yaml` | screener `RuleFactory` | `screener-strategy-v1` / `screener-profile-v1` |

두 가지 비대칭/중복:

1. **저장 위치 비대칭** — per-ticker·segment 는 `governance/`(선언적 SSoT)에, global 만 `domains/screener/config/`(엔진 내부)에 있다.
2. **스키마 중복** — 셋 다 사실상 동일한 `required_enrichments + cutoff rule-tree` shape 인데 스키마가 3종이다.

*적용(application)* 은 이미 통합돼 있다 — `SegmentResolver` 가 default(global) + segment + per-ticker 를 `MergeEngine` 으로 합성한다(ADR-0012, `--use-segments`, screener/universe wiring). 그러나 *저작(authoring)/저장* 은 분산돼 있다.

3개 렌즈(초기공수 / 유지·확장 / 인지부하) 분석 결과:

- **Q2 (전 tier `governance/` 통합 + 스키마 통합)**: 인지부하에서 큰 이득(유저·에이전트 단일 멘탈 모델), 유지·확장 순이익, 초기공수 중간. → **추진**.
- **Q3 (per-ticker 를 `selector=ticker` leaf segment 로 통합)**: 핵심 이득(per-ticker 가 segment 와 동일 merge 로 합성)이 **이미 `SegmentResolver.per_ticker_for` 주입으로 달성**됨. 추가 비용 — identity 를 cohort-property 선택속성 namespace 에 넣는 개념 오염, O(1) 직접조회 → O(tickers×segments) 퇴화, `domains/policy` 생산 파이프라인 blast radius, per-ticker 디렉토리 locality/감사성 상실. → **보류**.

## Decision

1. **저장 단일화 (Q2-storage).** global 정책(strategy / profile / hard_guards)을 `domains/screener/config/` 에서 `governance/` 산하로 이전한다. 모든 *선언적* 정책 tier 가 `governance/` 단일 루트에 거주 → 버저닝(`v<N>.yaml` + G20)·provenance·audit 스캔 단일화. 디렉토리 배치(`governance/strategies/` 또는 `governance/global/`)는 구현 시 확정.

2. **스키마 통합 (Q2-schema).** per-ticker / segment_profile / global profile 의 공통 `required_enrichments + cutoff_rules` shape 를 **`scope` 필드를 가진 단일 enrich-cutoff 스키마**로 수렴한다 (`scope ∈ {global, segment, ticker}`). 기존 `enrich-cutoff-profile-v1` / `segment-profile-v1` / `screener-profile-v1` → 단일 스키마. `screener-strategy-v1` 의 조합(`profile_ref`)·상수(`constants`: tax_rate / cache TTL)는 global scope 메타로 흡수하거나 별도 유지 — 구현 시 확정(ADR-0006 fat-contract shape 는 유지, `scope` 는 메타 필드 추가일 뿐).

3. **엔진 결합은 별개 — 본 결정은 저작/저장의 통합이다.** global cutoff *평가* 는 여전히 screener `RuleFactory`(metric_path resolver + `HardGuardWrapper` G13 + scoring methods registry)가 소유한다. 스토리지 이동이 엔진 통합을 의미하지 않는다. `hard_guards`(G13 잠금)는 screener-엔진 개념이지만 정책 거버넌스 성격도 있어 `governance/` 로 이전하되 `RuleFactory` 가 계속 소비.

4. **global = root/default segment 표현 (선택적, 적용 통합 명시화).** global 을 `selector = match-all` 인 root segment 로 표현해 `SegmentResolver.default_contribution` 으로 주입하는 경로를 허용한다. precedence(general→specific) 가 global → segment → per-ticker 로 일관되게 드러난다. (단 per-ticker 는 결정 5 에 따라 segment 로 만들지 않는다.)

5. **per-ticker → leaf segment 추상화는 보류 (Q3 deferred).** per-ticker 는 **identity-scoped 직접조회 tier** 로 유지하고 `_shared/profile_registry` 도 잔존시킨다. 근거:
   - (a) per-ticker 가 segment 와 합성되는 이득은 이미 `SegmentResolver.per_ticker_for` + `per_ticker_merge` 로 달성됨 (추가 추상화 없이 성립).
   - (b) ticker(identity)를 cohort-property 선택속성 namespace(`attributes.SELECTION_ATTRIBUTES`)에 넣으면 개념 오염 — namespace 는 의도적으로 identity 를 배제.
   - (c) O(1) 직접조회 → 모든 ticker 마다 N 개 leaf selector 평가하는 O(tickers×segments) 퇴화 (단락 인덱스 추가 비용).
   - (d) `domains/policy` 생산 파이프라인(`policy-profiler` → `_profile-draft` → `--commit-draft`)이 segment 를 emit 하도록 개편하는 blast radius.
   - (e) per-ticker 전용 디렉토리(`profiles/<ticker>/`)의 locality/감사성 상실.
   - 구체적 필요(예: per-ticker override 가 entry별 선언 merge 연산자를 꼭 써야 함) 발생 시 재검토.

## Consequences

- **구현 보류(planned).** 본 ADR 은 *방향 결정* 이다. 마이그레이션은 후속 작업:
  - screener config YAML 이전 + `screener._boundary` 로더 repoint + path helper(`infrastructure/_common/utils.py`) + `tests/architecture/test_governance_purity.py` 갱신.
  - 스키마 통합: `scope` 필드 추가한 단일 serde/registry 로 수렴 + 소비자(universe/screener) 로더 갱신 + **회귀 parity 증명**(flag OFF byte-parity, ADR-0012 와 동일 원칙).
- **인지부하↓** — "모든 정책은 `governance/`, scope 3단(global/segment/ticker), precedence 로 해소". 유저·에이전트 단일 멘탈 모델. (이 ADR 의 1순위 동기.)
- **위험** — `governance/` 가 "엔진 기본 config(hard_guards/scoring)"와 "외부 override"를 혼재하게 됨 → `governance/` = 선언적 SSoT 경계가 흐려질 수 있음. `scope` 필드 + 하위 디렉토리 분리로 완화.
- **profile_registry 잔존** — per-ticker(ticker-scope) 직접조회 tier 로 유지 (Q3 보류와 일관). 폐기하지 않는다.

## Alternatives considered

- **현상 유지(3 tier 분산).** 기각 — 저장 비대칭 + 스키마 3중화로 인한 인지부하.
- **Q3: per-ticker 까지 leaf segment 통합.** 보류 (상기 결정 5 근거) — over-abstraction / degenerate selector, 순증분 이득이 이미 주입 seam 으로 달성됨.
- **엔진까지 통합 (global cutoff 를 `_shared` 로).** 기각/범위 외 — global 은 screener `metric_path` resolver / `HardGuardWrapper` 에 본질 의존. `_shared` 로 옮기면 bc-independence(불변식 A) 위반.

## Implementation (2026-06-13)

구현 완료. 핵심 결과:

1. **저장 단일화.** 전 정책 tier 를 `governance/policy/` 단일 부모로 통합:
   - `governance/policy/profiles/` (per-ticker, scope=ticker) ← 구 `governance/profiles/`
   - `governance/policy/segments|concepts|segment_profiles/` ← 구 `governance/{...}`
   - `governance/policy/global/{strategies,profiles,hard_guards.yaml}` ← 구 `domains/screener/config/`
   - 경로 해석은 `infrastructure/_common/utils.py` helper(`profiles_dir`/`segments_dir`/`concepts_dir`/`named_profiles_dir` + 신규 `global_policy_dir`)에서 단일 변경 (env var override 이름 유지). screener `_boundary._config_root()` → `global_policy_dir()`.

2. **스키마 단일화.** 신규 `domains/_shared/policy_profile/`(`PolicyProfile` + serde + `PolicyProfileSchemaError`)가 **on-disk 스키마(`policy-profile-v1`) + serde 의 단일 권위**. `scope ∈ {global, segment, ticker}` + `key`(ticker or name) + `required_enrichments`/`cutoff_rules`/`qualitative_lenses?`/`provenance?`. legacy 3 스키마(`enrich-cutoff-profile-v1`/`segment-profile-v1`/`screener-profile-v1`)는 마이그레이션 게이트로 read 가능. `EnrichCutoffProfile`(scope=ticker) / `PolicyContribution`(merge-slice)는 통합 타입의 **scope별 view** 로 유지 — `profile_registry.serde`/`segment_registry.serde` 가 `policy_profile.serde` 에 위임·투영. `PolicyProfileSchemaError` 는 `ProfileSchemaError`+`SegmentSchemaError` 양쪽 상속 → 기존 except 절 호환.

3. **엔진 결합 불변(decision 3 준수).** global cutoff *평가* 는 여전히 screener `RuleFactory` 소유. 통합 YAML(scope=global, `cutoff_rules:`)은 screener `_boundary.load_profile` 어댑터가 RuleFactory 가 기대하는 `{"rule": ...}` shape 로 투영. golden parity test 로 빌드된 Rule 트리가 마이그레이션 전과 byte-identical 임을 고정.

4. **global = root segment(decision 4).** screener `--use-segments` ON 에서 전략의 확장된 global cutoff 를 `SegmentResolver.default_contribution` 으로 주입 → precedence global→segment→per-ticker. flag OFF 는 byte-parity. **universe 비대칭(구현 발견)**: universe 는 required_enrichments 만 union 하는데 whole-universe global *enrichment* 산출물이 없어(quality_floor.required_enrichments=[], global=cutoff 전용) `default_contribution` seam 은 두되 None 주입.

5. per-ticker 는 `governance/policy/profiles/` 직접조회 tier 로 유지(Q3 보류 일관). `profile_registry` 잔존.

검증: hermetic 전체 suite green(파리티 보존) + global profile golden parity + DART '사업의 내용' 라이브 추출 보강(상호참조 회피). 본 ADR 의 "구현 보류" 후속 작업이 모두 완료됨.

## Supersedes / Superseded-by

- **Extends** ADR-0002(governance/config ownership axis) — global 정책 위치를 ownership axis 관점에서 `governance/` 로 재배치하는 후속.
- **Extends** ADR-0012(segment 계층) — 적용 통합(SegmentResolver)을 저작 통합으로 확장.
- Supersede 없음 (append-only).
