# Sources — DiscoverySource Plugin

## 공통 인터페이스 (`sources/base.py`)

```python
@dataclass(frozen=True)
class DiscoveryContext:
    clock: AsOfClock
    env: Mapping[str, str]

@dataclass(frozen=True)
class SourceResult:
    entries: tuple[UniverseEntry, ...]
    warnings: tuple[str, ...]
    degraded: bool = False

class DiscoverySource(ABC):
    name: str
    source_category: str
    @classmethod
    @abstractmethod
    def from_spec(cls, spec: dict) -> "DiscoverySource": ...
    @abstractmethod
    def discover(self, ctx: DiscoveryContext) -> SourceResult: ...
```

## 카탈로그 (6 source)

| type | 인스턴스 name | source_category | 외부 IO | 특이사항 |
|---|---|---|---|---|
| `literal_list` | `manual_addition` | `manual_addition` | 없음 | items_ref → `manual_additions.yaml` |
| `holding_company` | `holding_company` | `holding_company` (entries 빈 tuple) | DART | **의도된 비대칭** — audit log 만 산출 |
| `dart_disclosure_filter` | `treasury_action` | `treasury_action` | DART pblntf_ty=B | priority_groups: cancellation |
| `dart_disclosure_filter` | `spin_off_or_merger` | `spin_off_or_merger` | DART pblntf_ty=B | keyword_groups: spin_off + merger |
| `dart_disclosure_filter` | `activist_filing` | `activist_filing` | DART pblntf_ty=D | annotate_filers: known 펀드 |
| `preferred_share_pair_seed` | `preferred_share_pair` | `preferred_share_pair` | DART | metadata 에 common/preferred/market |

## 등록 패턴

```python
SOURCE_TYPES: dict[str, type[DiscoverySource]] = {}
def register_source(name: str):
    def deco(cls):
        SOURCE_TYPES[name] = cls
        return cls
    return deco
```

## Factory dispatch

```python
def build_source(spec: dict) -> DiscoverySource:
    type_name = spec["type"]
    cls = SOURCE_TYPES.get(type_name)
    if cls is None:
        raise ValueError(f"unknown source type: {type_name}")
    return cls.from_spec(spec)
```

`factory.py` 의 top-level import 들이 각 source 모듈을 로드 → `@register_source` 부작용 트리거. 신규 source 파일 추가 시 `factory.py` 에 import 1줄 추가 필수.

## 신규 Source 추가 절차

1. `sources/{name}.py` 에 `@register_source("type_name")` + DiscoverySource 상속
2. `sources/factory.py` top-level import 1줄
3. `config/sources.yaml` 의 `sources:` 에 `type: type_name` entry
4. 필요 시 `config/{sub_config}.yaml` 신설 + `_boundary.load_sub_config`
5. 필요 시 외부 의존 → `_boundary.py` + `03-boundaries.md` 갱신
