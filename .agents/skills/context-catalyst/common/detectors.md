# Detectors — CatalystDetector Plugin

## 공통 인터페이스 (`detectors/base.py`)

```python
@dataclass(frozen=True)
class DetectContext:
    env: Mapping[str, str]
    universe: Mapping[str, str]         # {ticker: name}
    universe_market: Mapping[str, str]  # {stock_code: market}
    date: str                           # YYYY-MM-DD
    fetched_at: str                     # ISO_KST
    allow_yahoo: bool = False

@dataclass(frozen=True)
class DetectResult:
    events: tuple[CatalystEvent, ...]
    warnings: tuple[str, ...]

class CatalystDetector(ABC):
    name: str
    enabled: bool
    @classmethod
    @abstractmethod
    def from_spec(cls, spec: dict) -> "CatalystDetector": ...
    @abstractmethod
    def detect(self, ctx: DetectContext) -> DetectResult: ...
```

구현 계약: `@dataclass(frozen=True)` + `@register_detector("type_name")` + name/enabled 필드 + `from_spec` + `detect`.

## 카탈로그 (6 detector)

| type key | 클래스 | catalyst_type | trigger_class | 외부 IO | 특이사항 |
|---|---|---|---|---|---|
| `treasury_share_cancellation` | `TreasuryCancellationDetector` | `treasury_share_cancellation` | `a_type` | DART pblntf_ty=B via `scan_disclosures` | keyword `("주식소각","자기주식소각","이익소각")` |
| `spin_off_or_merger` | `SpinOffMergerDetector` | `spin_off_announcement` 또는 `merger_announcement` | `a_type` | DART pblntf_ty=B via `scan_disclosures` | 2 keyword group → `catalyst_type = matched_group` |
| `activist_5pct` | `Activist5pctDetector` | `activist_5pct_filing` | `d_type` | DART pblntf_ty=D via `scan_disclosures` | **augment-only (G15)**; optional known-funds filter |
| `index_deletion` | `IndexDeletionDetector` | `index_deletion` | `b_type` | DART pblntf_ty=I via `io/index_deletion_fetch` | inline G14 gate + `seen` dedup |
| `earnings_panic` | `EarningsPanicDetector` | `earnings_panic` | `b_type` | DART + KIS (Yahoo fallback) via `io/earnings_panic_fetch` | `drop_threshold = -abs(one_day_drop_min)` |
| `nav_discount_narrowing` | `NavDiscountNarrowingDetector` | `nav_discount_narrowing` | `a_type` | `domains/_shared/nav_history` | parents = config holding_companies |

## A/B/D-type taxonomy

- **A-type** (자사주소각 / 분할 / NAV 좁힘): treasury / spin_off / nav_discount → `trigger_class="a_type"`
- **B-type** (forced selling / index 편출 / panic): index_deletion / earnings_panic → `b_type`
- **D-type** (행동주의): activist_5pct → `d_type` (augment-only; G15 — 단독 trigger 불가)

## 등록 패턴

```python
DETECTOR_TYPES: dict[str, type[CatalystDetector]] = {}
def register_detector(name: str):
    def deco(cls):
        if name in DETECTOR_TYPES:
            raise ValueError(f"detector type '{name}' already registered")
        DETECTOR_TYPES[name] = cls
        return cls
    return deco
```

## 신규 Detector 추가 절차

1. `detectors/{name}.py` 에 `@register_detector("{type_name}")` + `CatalystDetector` ABC 상속
2. `detectors/factory.py` top-level import 1줄
3. `config/detectors.yaml` 의 `detectors:` 에 `type: {type_name}` entry (순서 중요)
4. DART 패턴이면 `_shared/adapters/disclosure_scan` 재사용
5. G14 (universe membership) gate 적용
