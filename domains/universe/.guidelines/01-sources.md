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
    degraded: bool = False   # progressive degrade retry 발동 여부

class DiscoverySource(ABC):
    name: str
    source_category: str

    @classmethod
    @abstractmethod
    def from_spec(cls, spec: dict) -> "DiscoverySource": ...

    @abstractmethod
    def discover(self, ctx: DiscoveryContext) -> SourceResult: ...
```

## 카탈로그 (Run 6 시점)

| type | 인스턴스 name | source_category 산출 | 외부 IO | 특이사항 |
|---|---|---|---|---|
| `literal_list` | `manual_addition` | `manual_addition` | 없음 | items_ref → `manual_additions.yaml` |
| `holding_company` | `holding_company` | `holding_company` (entries 는 빈 tuple) | DART (corp index + 사업보고서) | **의도된 비대칭** — audit log 만 산출 (`subsidiaries-audit-{date}.json`), entries 빈 tuple |
| `dart_disclosure_filter` | `treasury_action` | `treasury_action` | DART /api/list (pblntf_ty=B) | priority_groups: cancellation → priority_note |
| `dart_disclosure_filter` | `spin_off_or_merger` | `spin_off_or_merger` | DART /api/list (pblntf_ty=B) | keyword_groups: spin_off + merger → metadata.kind 로 구분 |
| `dart_disclosure_filter` | `activist_filing` | `activist_filing` | DART /api/list (pblntf_ty=D) | annotate_filers: known 펀드 → metadata.known_activist=True |
| `preferred_share_pair_seed` | `preferred_share_pair` | `preferred_share_pair` | DART (auto_discover=true 시) | metadata 에 common / preferred / market — `SpreadZScoreEnricher` 가 read |

## 등록 패턴 (`sources/registry.py`)

```python
SOURCE_TYPES: dict[str, type[DiscoverySource]] = {}

def register_source(name: str):
    def deco(cls):
        if name in SOURCE_TYPES:
            raise ValueError(f"source type '{name}' already registered")
        SOURCE_TYPES[name] = cls
        return cls
    return deco
```

신규 source 의 `@register_source("type_name")` decorator 가 부착되어야 factory dispatch 가능.

## Factory dispatch (`sources/factory.py`)

```python
def build_source(spec: dict) -> DiscoverySource:
    type_name = spec["type"]
    cls = SOURCE_TYPES.get(type_name)
    if cls is None:
        raise ValueError(f"unknown source type: {type_name}")
    return cls.from_spec(spec)
```

`factory.py` 의 top-level import 들이 각 source 모듈을 로드 → `@register_source` 부작용 트리거. 신규 source 파일 추가 시 `factory.py` 에 import 1줄 추가 필수.

## DartDisclosureFilter 통합 원칙 (Pain 1/2 해결)

원래 `alpha_factory/universe.py` 의 `discover_treasury_actions` / `discover_spin_off_announcements` / `discover_activist_filings` 3 함수가 35-60줄씩 retry 로직 + dedup + UniverseEntry build 를 복제하던 것을 `dart_disclosure_filter.py` 의 단일 클래스로 흡수. 3 인스턴스의 차이는:

- `pblntf_ty` (B=정기공시, D=지분공시)
- `keyword_groups` (kind 명 → keywords tuple)
- `source_category` (treasury_action / spin_off_or_merger / activist_filing)
- `annotate_filers` (activist 의 known 펀드 마커)
- `priority_groups` (treasury 의 cancellation_priority_note)

5/14 incident progressive degrade 패치는 본 클래스의 retry loop 한 곳에서만 갱신.

## HoldingCompanySource 의 비대칭 명시화

`HoldingCompanySource.discover()` 는 항상 빈 `entries=()` 반환 + audit log 만 산출. *의도된 비대칭* — 부모 ticker 의 universe 진입은 사용자가 `manual_additions.yaml` 에 명시. NAV 할인 계산은 `enrichers/nav_discount.py` 가 별도 책임 (Run 5).

향후 (Run 5 이후 검토) parent ticker 를 자동 emit 하는 mode 추가 가능 — 단 G14 (manual map 외 자동 추가 금지) 위반 가능성 신중 검토.

## 신규 Source 추가 절차

1. `sources/{name}.py` 에 `@register_source("type_name")` decorator 가 부착된 `@dataclass(frozen=True)` 클래스 (`DiscoverySource` ABC 상속)
2. `sources/factory.py` 의 top-level import 에 1줄 추가
3. `config/sources.yaml` 의 `sources:` 에 `type: type_name` entry 추가
4. (필요 시) `config/{sub_config}.yaml` 신설 + `_boundary.load_sub_config` 로 로드
5. (필요 시) 외부 의존이 추가되면 `_boundary.py` + `03-boundaries.md` + `README.md` 갱신
6. `domains/universe/tests/unit/test_universe_sources.py` 또는 신규 `test_{name}_source.py` 에 케이스 추가
7. 본 문서의 카탈로그 표 갱신
