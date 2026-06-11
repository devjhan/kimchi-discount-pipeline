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

`EnrichmentResult`: `attributes`, `citations`, `warnings`, `skip_reason` (None → success)

## 카탈로그 (2 enricher)

| type | 인스턴스 name | applies_to | 외부 IO | 산출 attributes |
|---|---|---|---|---|
| `nav_discount` | `nav_discount` | `{holding_company}` | KIS 현재가 | parent_market_cap / nav_estimate / discount_pct / subsidiaries |
| `spread_zscore` | `spread_zscore` | `{preferred_share_pair}` | KIS 일봉 (+ Yahoo fallback) | common_close / preferred_close / z_score / catalyst_flag / n_observations / ... |

## 등록 패턴

```python
ENRICHER_TYPES: dict[str, type[Enricher]] = {}
def register_enricher(name: str):
    def deco(cls):
        ENRICHER_TYPES[name] = cls
        return cls
    return deco
```

## applies_to 매칭

- `entry.source_category not in enricher.applies_to` → pass-through (no warning)
- 어느 source_category 와도 매칭 안 됨 (orphan) → audit warning `enricher_orphan`
- 다중 enricher 동일 source_category attach 가능 (`enrichments` dict 가 name 별 저장)

## G6 보장 — 산식 single source

- NAV 합산 `Σ (sub_market_cap × ownership_pct)` 는 `nav_discount.py:_compute_nav` 단독
- z-score `(current - mean) / std` 는 `spread_zscore.py:_compute_zscore` 단독
- LLM skill 은 본 attributes 를 *인용* 만, 재계산 금지

## 신규 Enricher 추가 절차

1. `enrichers/{name}.py` 에 `@register_enricher("type_name")` + `Enricher` ABC 상속
2. `applies_to` 필드 명시
3. `enrichers/factory.py` top-level import 1줄
4. `config/enrichers.yaml` 의 `enrichers:` 에 `type: type_name` entry
