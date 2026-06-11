# Catalyst BC Overview

Stage 3 Catalyst Event Scan — Stage 2 quality-pass 종목에 대해 catalyst trigger (A-type 자사주소각/분할/NAV좁힘 · B-type forced-selling/panic · D-type 행동주의) 를 6 `CatalystDetector` plugin 으로 fan-in 탐지.

## 4 Anchor

1. **`detectors/factory.build_detector` 단일 진입점** — 모든 CatalystDetector 인스턴스화는 본 함수 통과
2. **`detectors/registry.register_detector` decorator + `DETECTOR_TYPES` dict** — 중복 등록은 `ValueError`
3. **`_boundary.py` 단일 외부 게이트** — infra 직접 import 금지 (절대적)
4. **공유 clock SSoT** — `domains._shared.time.clock.AsOfClock`; 3 DART detector 는 `_shared/adapters/disclosure_scan` 공유 (F-16)

## 패키지 구조

```
domains/catalyst/
  _boundary.py          # 외부 의존 단일 게이트 (DART / KIS / Yahoo / 경로 / env)
  detectors/            # CatalystDetector 플러그인 (6)
    base.py / registry.py / factory.py
    treasury_cancellation.py   # A-type
    spin_off_merger.py         # A-type
    activist_5pct.py           # D-type (augment-only, G15)
    index_deletion.py          # B-type
    earnings_panic.py          # B-type
    nav_discount_narrowing.py  # A-type
  domain/event.py       # CatalystEvent (frozen)
  application/scan_catalysts.py  # orchestrator (+ G15 augment)
  io/                   # trail_loader, index_deletion_fetch, earnings_panic_fetch
  audit/                # G6/G7 invariants + violation log
  config/detectors.yaml # detector 리스트 + 임계값
  main.py               # Stage 3 CLI
```

## 외부 연결점

| 방향 | 인터페이스 | 게이트 |
|---|---|---|
| 입력 (DART 공시) | A/B/D-type 공시 list scan | `_boundary.dart_iter_disclosures` → `_shared/adapters/disclosure_scan` (F-16) |
| 입력 (KIS price) | 어닝 패닉 일별 OHLCV | `_boundary.kis_fetch_daily_ohlcv` |
| 입력 (Yahoo) | KIS fallback | `_boundary.yahoo_fetch_daily_ohlcv` |
| 입력 (universe/quality) | `$TRAIL_TODAY/01-universe.json` · `02-quality-filter.json` | `_boundary.resolve_trail_dir` |
| 입력 (config/env) | `config/detectors.yaml` · `.env` | self-contained / `_boundary.load_env` |
| 출력 (Stage 3) | `$TRAIL_TODAY/03-catalyst-events.json` | `_boundary.write_output_safely` (G20) |

## DDD 규약

- 다른 catalyst 모듈은 `infrastructure.*` / `os.environ` 직접 사용 금지 → `_boundary.py` 통과
- 예외 — `domains._shared.*` 직접 import 가능 (clock / calendar / ports / adapters(disclosure_scan) / nav_history / audit)
- `infrastructure.*` 직접 import 예외는 **없음** (그 gate 는 절대적)
- 신규 detector 추가 = `detectors/{name}.py` (`@register_detector`) + `factory.py` import + `config/detectors.yaml` 한 줄

## 검증

```bash
grep -rn "from infrastructure\|import infrastructure" domains/catalyst/ --include="*.py" | grep -v _boundary.py
# → 0
```
