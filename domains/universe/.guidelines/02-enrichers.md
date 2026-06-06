# Enrichers — Per-source Attribute Attachment

## 공통 인터페이스 (`enrichers/base.py`)

```python
@dataclass(frozen=True)
class EnrichContext:
    clock: AsOfClock
    env: Mapping[str, str]
    allow_yahoo: bool = False

class Enricher(ABC):
    name: str
    applies_to: frozenset[str]   # 매칭 source_category 집합

    @classmethod
    @abstractmethod
    def from_spec(cls, spec: dict) -> "Enricher": ...

    @abstractmethod
    def enrich(self, entry: UniverseEntry, ctx: EnrichContext) -> EnrichmentResult: ...
```

`EnrichmentResult`:
```python
@dataclass(frozen=True)
class EnrichmentResult:
    attributes: Mapping[str, Any]
    citations: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    skip_reason: str | None = None   # not None → enrichment 미실행
```

## 카탈로그 (Run 6 시점)

| type | 인스턴스 name | applies_to | 외부 IO | 산출 attributes |
|---|---|---|---|---|
| `nav_discount` | `nav_discount` | `{holding_company}` | KIS 현재가 | `parent_market_cap` / `nav_estimate` / `discount_pct` / `subsidiaries` |
| `spread_zscore` | `spread_zscore` | `{preferred_share_pair}` | KIS 일봉 (+ Yahoo fallback) | `common_close` / `preferred_close` / `current_spread_pct` / `mean_spread_pct` / `std_spread_pct` / `z_score` / `z_min` / `catalyst_flag` / `n_observations` / `price_source` / `last_observation_date` |

## 등록 패턴 (`enrichers/registry.py`)

```python
ENRICHER_TYPES: dict[str, type[Enricher]] = {}

def register_enricher(name: str):
    def deco(cls):
        if name in ENRICHER_TYPES:
            raise ValueError(f"enricher type '{name}' already registered")
        ENRICHER_TYPES[name] = cls
        return cls
    return deco
```

## applies_to 매칭 규약

`application/build_universe.py` 의 enrichment phase:

```python
for entry in kept_entries:
    enriched = EnrichedEntry.from_base(entry)
    for enricher in enrichers:
        if entry.source_category not in enricher.applies_to:
            continue       # pass-through
        result = enricher.enrich(entry, ctx)
        enriched = enriched.with_enrichment(enricher.name, result)
```

- `applies_to` 가 entry.source_category 와 disjoint → enrichment 미실행 (pass-through, no warning)
- `applies_to` 가 sources.yaml 의 어느 source_category 와도 매칭 안 됨 (orphan) → audit warning (`enricher_orphan`), entry 미생성이라 영향 없음
- 다중 enricher 가 같은 source_category 에 attach 가능 (예: holding_company → nav_discount + future quality_lens) — `enrichments` dict 가 name 별로 별도 저장

## skip vs success

`EnrichmentResult.skip_reason is not None` → `EnrichedEntry.enrichment_skips[enricher.name]` 에 기록, `enrichments[enricher.name]` 은 미설정. 자주 발생하는 skip 케이스:

- KIS_APP_KEY / KIS_APP_SECRET 부재 (NavDiscount / SpreadZScore 공통)
- subsidiaries.yaml 에 ticker 매핑 부재 (NavDiscount)
- entry.metadata 에 common / preferred ticker 부재 (SpreadZScore)
- 가격 series fetch 완전 실패 (SpreadZScore — Yahoo fallback 도 실패한 경우)
- min_observations 미달 (SpreadZScore — z_score=None 이지만 skip 은 아님; attributes 부분 채움)

## 신규 Enricher 추가 절차

1. `enrichers/{name}.py` 에 `@register_enricher("type_name")` decorator + `@dataclass(frozen=True)` 클래스 (`Enricher` ABC 상속)
2. `applies_to` 필드 명시 — 매칭 source_category set
3. `enrichers/factory.py` 의 top-level import 에 1줄 추가
4. `config/enrichers.yaml` 의 `enrichers:` 에 `type: type_name` entry 추가
5. 외부 의존이 추가되면 `_boundary.py` + `03-boundaries.md` + `README.md` 갱신
6. `domains/universe/tests/unit/test_universe_enrichers.py` 에 케이스 추가
7. 본 문서의 카탈로그 표 갱신

## G6 보장 — 산식 single source

- NAV 합산 `Σ (sub_market_cap × ownership_pct)` 는 `nav_discount.py:_compute_nav` 단독
- z-score `(current - mean) / std` 는 `spread_zscore.py:_compute_zscore` 단독
- main.py / build_universe.py / Stage 2+ 도메인 어디에서도 본 산식 재구현 금지
- LLM skill (`investment-stage2-quality-lens` 등) 은 본 attributes 를 *인용* 만, 재계산 금지
