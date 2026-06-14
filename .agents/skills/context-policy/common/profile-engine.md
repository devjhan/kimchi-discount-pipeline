# Profile Engine — PolicyEngine Protocol + EnrichCutoffProfile

## PolicyEngine Protocol (ports/llm.py)

```python
class PolicyEngine(Protocol):
    def analyze(self, trigger: Trigger, *, evidence: tuple[str, ...]) -> ResearchOutput: ...
```

구현체 없음 — `application/analyze.run_analysis(trigger, engine, *, evidence=())` 가 Protocol 에만 의존. production research 는 `investment-policy-profiler` skill (phase 2) — **commit 안 함**.

## EnrichCutoffProfile — ADR-0006 "fat contract"

`_shared.profile_registry.schema.EnrichCutoffProfile` (`@dataclass(frozen=True)`) — 통합 `policy-profile-v1`(scope-tagged) 의 **scope=ticker in-memory view** (on-disk serde 단일 권위 = `domains/_shared/policy_profile/`; segment merge-slice 는 `PolicyContribution` = scope=segment view):

```python
ticker: str                       # "KR:NNNNNN"
schema_version: str               # == SCHEMA_VERSION
profile_version: int              # monotonic (1, 2, 3, ...)
required_enrichments: tuple[str, ...]   # universe 가 적용할 enricher name
cutoff_rules: Mapping[str, Any]   # screener Rule dict-tree ('type' 키 필수)
provenance: Provenance            # commit 근거 + G7 citations
description: str = ""             # D-CFG-1 대응
```

`__post_init__` 검증: 빈/`:` 없는 ticker / `profile_version < 1` / `schema_version != SCHEMA_VERSION` / cutoff_rules 에 `"type"` 키 부재 → `ProfileSchemaError`. **rule 의미(metric_path/op) 는 검증 안 함** — screener `RuleFactory` 책임.

### 단일 단위 (ISP — ADR-0006)

enrich+cutoff 를 분리하지 않는 결정: 전체 profile 에 의존하는 것이 의도된 coupling. screener completeness gate 가 `required_enrichments` 역참조 (누락 → `verdict="caution"`).

## profile_registry API

`domains._shared.profile_registry.registry.ProfileRegistry` (`root: Path`):

```python
load_latest(ticker) -> EnrichCutoffProfile | None
load_version(ticker, version) -> EnrichCutoffProfile
list_versions(ticker) -> tuple[int, ...]
commit(profile, *, writer) -> Path    # versioned write, never overwrite (G20)
```

serde: `to_dict(p)` / `from_dict(raw)` — on-disk serde 단일 권위는 `domains/_shared/policy_profile/serde`, profile_registry serde 는 `EnrichCutoffProfile`(scope=ticker view) ↔ `PolicyProfile` 투영 후 위임. `from_dict` 가 schema gate (미지원 `schema` → reject; legacy `enrich-cutoff-profile-v1` 은 마이그레이션 수용).

## governance/policy/profiles/ 파일 포맷

통합 `policy-profile-v1` (per-ticker 파일은 `scope: ticker`):

```yaml
schema: policy-profile-v1
version: <int>
description: <str>
scope: ticker
key: KR:NNNNNN
required_enrichments: [<enricher names>]
cutoff_rules: { type: ..., ... }
provenance:
  committed_at: <iso kst>
  committed_by: policy|manual|regression-fixture
  trigger: "filing:rcept_no=..." | "news:..." | "manual"
  citations: ["DART@<iso>=<value>", ...]
  rationale_ko: <str>
```

layout: `governance/policy/profiles/<ticker_dir>/v<N>.yaml`.

## 정책 계층 통합 (ADR-0013, 구현 완료 2026-06-13)

profile 은 3 tier — per-ticker(`governance/policy/profiles/ticker/`, 본 BC) · segment(`governance/policy/profiles/segment/` + 멤버십 `policy/segments|concepts/`, ADR-0012) · global(`governance/policy/profiles/global/`). 조합/floor 는 `policy/strategies/` + `policy/hard_guards.yaml` (구 `domains/screener/config/`). ADR-0013→0014 결과:

- **완료(Q2)**: 전 tier 가 `governance/policy/` 산하로 이전 + 세 tier 의 `required_enrichments + cutoff_rules` shape 가 `scope∈{global,segment,ticker}` tagged 단일 `policy-profile-v1` 스키마로 수렴. on-disk serde 단일 권위 = `domains/_shared/policy_profile/`. `EnrichCutoffProfile` 은 그 scope=ticker view, `PolicyContribution` 은 scope=segment merge-slice view. global profile YAML 은 `rule:` 키 대신 `cutoff_rules:` 키 사용(scope: global).
- **보류(Q3)**: per-ticker 를 `selector=ticker` leaf segment 로 추상화하지 **않음**. per-ticker 는 identity-scoped 직접조회 tier 로 유지, `ProfileRegistry` 잔존. (합성 이득은 이미 `SegmentResolver.per_ticker_for` 주입으로 달성.)

global cutoff *평가* 는 여전히 screener `RuleFactory` 소유 (스토리지만 이동, 엔진 통합 아님). screener `_boundary.load_profile` 이 통합 YAML 을 RuleFactory 가 기대하는 `{"rule": cutoff_rules}` shape 로 어댑트.
