# Detectors — CatalystDetector Plugin

## 공통 인터페이스 (`detectors/base.py`)

```python
@dataclass(frozen=True)
class DetectContext:
    env: Mapping[str, str]
    universe: Mapping[str, str]         # {ticker: name} — G14 membership + name lookup
    universe_market: Mapping[str, str]  # {stock_code: market}
    date: str                           # YYYY-MM-DD
    fetched_at: str                     # ISO_KST → event.detected_at
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

구현 계약: (1) `@dataclass(frozen=True)`; (2) `@register_detector("type_name")`;
(3) `name` / `enabled` 필드; (4) `from_spec(spec)` classmethod; (5) `detect(ctx)`.

## 카탈로그 (6 detector)

| type key | 클래스 | catalyst_type | trigger_class | 외부 IO | 특이사항 |
|---|---|---|---|---|---|
| `treasury_share_cancellation` | `TreasuryCancellationDetector` | `treasury_share_cancellation` | `a_type` | DART `pblntf_ty="B"` via `scan_disclosures` | keyword `("주식소각","자기주식소각","이익소각")`; `keep=ticker in universe` (G14); dedup `DART-{rcept_dt}-{rcept_no}` |
| `spin_off_or_merger` | `SpinOffMergerDetector` | `spin_off_announcement` 또는 `merger_announcement` | `a_type` | DART `pblntf_ty="B"` via `scan_disclosures` | 2 keyword group → `catalyst_type = matched_group`; dedup 에 `-{matched_group}`; window=max(spin_off, merger lookback) |
| `activist_5pct` | `Activist5pctDetector` | `activist_5pct_filing` | `d_type` | DART `pblntf_ty="D"` via `scan_disclosures` | **augment-only (G15)**; keyword `("주식등의대량보유상황",)`; optional `include_known_funds_only` / `known_activist_funds` 필터 (`flr_nm`); metadata `augment_only_note` |
| `index_deletion` | `IndexDeletionDetector` | `index_deletion` | `b_type` | DART `pblntf_ty="I"` via `io/index_deletion_fetch` | 구 `03-index-deletion.json` in-memory 흡수; inline G14 gate + `seen` dedup `INDEX-{rcept_dt}-{rcept_no}` |
| `earnings_panic` | `EarningsPanicDetector` | `earnings_panic` | `b_type` | DART `pblntf_ty="I"/"E"` + KIS 가격 (Yahoo fallback) via `io/earnings_panic_fetch` | `drop_threshold = -abs(one_day_drop_min)`; `universe_market` 비면 skip; dedup `EARNPANIC-{rcept_dt}-{rcept_no}` |
| `nav_discount_narrowing` | `NavDiscountNarrowingDetector` | `nav_discount_narrowing` | `a_type` | `domains/_shared/nav_history` (NOT `_boundary`) | parents = config `holding_companies` 또는 `list_parents()`; ≥2 history point 필요; 빈 parents → warning (early-run 정상); prod `holding_companies: []` |

### per-detector spec 필드 (`from_spec` + `config/detectors.yaml`)

- treasury: `name` / `enabled` / `lookback_days` (30)
- spin_off_or_merger: `name` / `enabled` / `spin_off_lookback_days` (60) / `merger_lookback_days` (60)
- activist_5pct: `name` / `enabled` / `lookback_days` (30) / `include_known_funds_only` (False) / `known_activist_funds` (())
- index_deletion: `name` / `enabled` / `lookback_days` (90)
- earnings_panic: `name` / `enabled` / `lookback_days` (30) / `one_day_drop_min` (0.10)
- nav_discount_narrowing: `name` / `enabled` / `delta_threshold` (-0.05) / `lookback_days` (60) / `holding_companies` (())

## 등록 패턴 (`detectors/registry.py`)

```python
DETECTOR_TYPES: dict[str, type[CatalystDetector]] = {}

def register_detector(name: str):
    def deco(cls):
        if name in DETECTOR_TYPES:
            raise ValueError(
                f"detector type '{name}' already registered: {DETECTOR_TYPES[name].__name__}"
            )
        DETECTOR_TYPES[name] = cls
        return cls
    return deco
```

## Factory dispatch (`detectors/factory.py`)

```python
def build_detector(spec: dict) -> CatalystDetector:
    # spec 은 dict, "type" / "name" 키 필수 (else ValueError)
    type_name = spec["type"]
    cls = DETECTOR_TYPES.get(type_name)
    if cls is None:
        raise ValueError(f"unknown detector type: '{type_name}'. registered: {sorted(DETECTOR_TYPES)}")
    return cls.from_spec(spec)
```

`factory.py` 의 top-level import 들이 6 detector 모듈을 로드 → `@register_detector` 부작용
트리거. 신규 detector 파일 추가 시 `factory.py` 에 import 1줄 추가 필수.

## A/B/D-type taxonomy 매핑

- **A-type** (자사주소각 / 분할 / NAV 좁힘): `treasury_share_cancellation` /
  `spin_off_announcement` / `merger_announcement` / `nav_discount_narrowing` → `trigger_class="a_type"`
- **B-type** (forced selling / index 편출 / panic): `index_deletion` / `earnings_panic` → `b_type`
- **D-type** (insider / activist): `activist_5pct_filing` → `d_type` (augment-only; G15 — 단독 trigger 불가)

## 신규 Detector 추가 절차

1. `detectors/{name}.py` 에 `@register_detector("{type_name}")` 부착된 `@dataclass(frozen=True)`
   클래스 (`CatalystDetector` ABC 상속) — `from_spec` / `detect` 구현
2. `detectors/factory.py` 의 top-level import 에 1줄 추가
3. `config/detectors.yaml` 의 `detectors:` 에 `type: {type_name}` entry 추가 (실행 순서 주의 — `02-scan.md`)
4. DART 패턴이면 `domains/_shared/adapters/disclosure_scan` 재사용 (window/retry/citation/매핑은 detector 잔류 — byte-parity)
5. G14 (universe membership) gate 적용 — `keep=ticker in ctx.universe`
6. `domains/catalyst/tests/unit/test_catalyst_detectors.py` 에 케이스 + golden snapshot 갱신
7. 본 문서 카탈로그 표 갱신
