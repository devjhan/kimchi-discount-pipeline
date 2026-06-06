# Profile Engine — PolicyEngine Protocol + EnrichCutoffProfile

## PolicyEngine 는 Protocol (구현은 skill)

`domains.policy.ports.llm.PolicyEngine(Protocol)` — 본 BC 에 구현체 없음:

```python
class PolicyEngine(Protocol):
    def analyze(self, trigger: Trigger, *, evidence: tuple[str, ...]) -> ResearchOutput: ...
```

산출은 **draft** = `ResearchOutput`. 구현 (Claude skill / API) 은 `_boundary` 뒤에서
composition root `main(engine=...)` 로 주입. `application/analyze.run_analysis(trigger, engine,
*, evidence=())` 는 `return engine.analyze(trigger, evidence=evidence)` 로 Protocol 에만 의존.
production research 는 `investment-policy-profiler` skill (phase 2) — **commit 안 함**.

## EnrichCutoffProfile — ADR-0006 "fat contract" 단일 정책 단위

`domains._shared.profile_registry.schema.EnrichCutoffProfile` (`@dataclass(frozen=True)`):

```python
ticker: str                       # "KR:NNNNNN"
schema_version: str               # == SCHEMA_VERSION
profile_version: int              # ticker 별 monotonic (1, 2, 3, ...)
required_enrichments: tuple[str, ...]   # universe 가 이 종목에 적용할 enricher name
cutoff_rules: Mapping[str, Any]   # screener Rule dict-tree (RuleFactory 소비, 'type' 키 필수)
provenance: Provenance            # commit 근거 + G7 citations
description: str = ""             # D-CFG-1 대응 (on-disk YAML description 미러)
```

`__post_init__` (수동 검증, `ProfileSchemaError` raise — pydantic 아님): 빈/`:` 없는 ticker /
`profile_version < 1` / `schema_version != SCHEMA_VERSION` / `cutoff_rules` 가 Mapping 아니거나
`"type"` 키 부재 시 reject. **rule 의미 (metric_path/op) 는 검증 안 함** — 그 권한은 screener
`RuleFactory`.

`Provenance` (frozen): `committed_at` / `committed_by` / `trigger` / `citations: tuple[str,...]=()` /
`rationale_ko: str=""`.

### 왜 단일 단위인가 (ISP — ADR-0006)

universe 는 사실상 `required_enrichments` 만, screener 는 `cutoff_rules` 만 쓰지만, 둘 다
*전체* profile 에 의존한다. **분리하지 않는** 결정: profile 은 enrich+cutoff 를 "한 호흡" 으로
정의하는 **단일 정책 단위**이며, whole-dependency 가 그 의도를 정직히 반영 (serde-split 비용 >
ISP 이득). screener 의 completeness gate 가 `required_enrichments` 를 역참조하는 것은 이 단일
단위의 *의도된 coupling* — 누락 enrichment ticker 는 `verdict="caution"` 으로 degrade.

## profile_registry API

`domains._shared.profile_registry.registry.ProfileRegistry` (`@dataclass(frozen=True)`, `root: Path`):

```python
load_latest(ticker) -> EnrichCutoffProfile | None   # 미등록 → None (Default No-Action); 손상 → ProfileSchemaError
load_version(ticker, version) -> EnrichCutoffProfile # 부재 → ProfileNotFoundError
list_versions(ticker) -> tuple[int, ...]            # 미등록 → ()
commit(profile, *, writer) -> Path                   # versioned write; <root>/<ticker_dir>/v<N>.yaml; never overwrite (G20)
```

serde (`profile_registry.serde`): `to_dict(p)` / `from_dict(raw)` — `from_dict` 가 schema gate
(미지원 `schema` → `ProfileSchemaError`; 기타 parse 실패도 wrap).

## governance/profiles/ 파일 포맷

(현재 `.gitkeep` 만 — cutover 前 dormant.) `serde.to_dict` 산출 YAML:

```yaml
schema: enrich-cutoff-profile-v1
version: <int>
description: <str>
ticker: KR:NNNNNN
required_enrichments: [<enricher names>]
cutoff_rules: { type: ..., ... }     # 'type' 키 필수
provenance:
  committed_at: <iso kst>
  committed_by: policy|manual|regression-fixture
  trigger: "filing:rcept_no=..." | "news:..." | "manual"
  citations: ["DART@<iso>=<value>", ...]
  rationale_ko: <str>
```

layout: `governance/profiles/<ticker_dir>/v<N>.yaml` (예: `KR_005930/v3.yaml`).
