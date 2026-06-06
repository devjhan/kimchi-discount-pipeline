# domains/catalyst — Stage 3 Catalyst Event Scan BC

투자 파이프라인 Stage 3 — Stage 2 quality-pass 종목에 대해 **catalyst trigger**
(A-type 자사주소각/분할 · B-type forced-selling/패닉 · D-type 행동주의) 를 탐지하는
bounded context (구 `alpha_factory` catalyst_scan). screener/universe 와 isomorphic
DDD: 각 catalyst 유형은 `CatalystDetector` 플러그인 (`@register_detector`).

## 패키지 구조

```
domains/catalyst/
  _boundary.py          # 외부 의존 단일 게이트 (DART / KIS / Yahoo / 경로 / env)
  detectors/            # CatalystDetector 플러그인 (fetch + 판정) — plugin family
    base.py / registry.py / factory.py
    treasury_cancellation.py   # A-type 자사주 소각
    spin_off_merger.py         # A-type 분할/합병
    activist_5pct.py           # D-type 5% 대량보유 (augment-only, G15)
    index_deletion.py          # B-type 인덱스 편출
    earnings_panic.py          # B-type 어닝 패닉 (KIS price drop)
    nav_discount_narrowing.py  # A-type NAV 할인 축소
  domain/event.py       # CatalystEvent (frozen)
  application/scan_catalysts.py  # orchestrator (+ G15 d_type augment/orphan)
  io/                   # nav_history_cache 등
  audit/                # G6/G7 invariants + violation log (universe pattern mirror)
  config/detectors.yaml # detector 리스트 + 임계값
  main.py               # Stage 3 CLI
```

새 detector 추가 = `detectors/{name}.py` (`@register_detector`) + `factory.py` import +
`config/detectors.yaml` 한 줄. `main` / `scan_catalysts` 수술 불요.

## 외부 연결점

| 방향 | 인터페이스 | 게이트 |
|---|---|---|
| 입력 (DART 공시) | A/B/D-type 공시 list scan | `_boundary.dart_iter_disclosures` → `_shared/adapters/disclosure_scan` (F-16) |
| 입력 (KIS price) | 어닝 패닉 일별 OHLCV | `_boundary.kis_fetch_daily_ohlcv` |
| 입력 (Yahoo) | KIS fallback 일별 OHLCV | `_boundary.yahoo_fetch_daily_ohlcv` (`resolve_allow_yahoo_fallback` 게이트) |
| 입력 (universe/quality) | `$TRAIL_TODAY/01-universe.json` · `02-quality-filter.json` | `_boundary.resolve_trail_dir` |
| 입력 (config/env) | `config/detectors.yaml` · `.env` | self-contained / `_boundary.load_env` |
| 출력 (Stage 3) | `$TRAIL_TODAY/03-catalyst-events.json` | `_boundary.write_output_safely` (G20) |

## Ports & Adapters

3 DART detector (treasury / spin_off / activist) 는 universe 와 공유하는
`domains/_shared/adapters/disclosure_scan.scan_disclosures` 를 채택 (F-16, 구 3중복제
소멸). `_boundary.dart_iter_disclosures` 를 `DisclosureSourcePort` 로 주입; G14 universe
게이트 + activist known-funds 필터는 `keep` 콜백, dedup-key/catalyst_type/citation 은
detector 잔류 (byte-parity — `tests/.../test_catalyst_golden.py` 가드).

패턴 본문: `domains/screener/.guidelines/05-boundaries.md` "Ports & Adapters".

## 검증

```bash
grep -rn "from infrastructure\|import infrastructure" domains/catalyst/ --include="*.py" | grep -v _boundary.py   # → 0
# catalyst golden snapshot (DART/KIS mock → 산출 byte-동일) 회귀 가드
```
