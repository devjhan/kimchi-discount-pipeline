# Profile Engine — PolicyEngine Protocol + EnrichCutoffProfile

## PolicyEngine Protocol (ports/llm.py)

```python
class PolicyEngine(Protocol):
    def analyze(self, trigger: Trigger, *, evidence: tuple[str, ...]) -> ResearchOutput: ...
```

구현체 없음 — `application/analyze.run_analysis(trigger, engine, *, evidence=())` 가 Protocol 에만 의존. production research 는 `investment-policy-profiler` skill (phase 2) — **commit 안 함**.

## EnrichCutoffProfile — ADR-0006 "fat contract"

`_shared.profile_registry.schema.EnrichCutoffProfile` (`@dataclass(frozen=True)`):

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

serde: `to_dict(p)` / `from_dict(raw)` — `from_dict` 가 schema gate (미지원 `schema` → reject).

## governance/profiles/ 파일 포맷

```yaml
schema: enrich-cutoff-profile-v1
version: <int>
description: <str>
ticker: KR:NNNNNN
required_enrichments: [<enricher names>]
cutoff_rules: { type: ..., ... }
provenance:
  committed_at: <iso kst>
  committed_by: policy|manual|regression-fixture
  trigger: "filing:rcept_no=..." | "news:..." | "manual"
  citations: ["DART@<iso>=<value>", ...]
  rationale_ko: <str>
```

layout: `governance/profiles/<ticker_dir>/v<N>.yaml`.
