# Macro BC Overview

Stage 0 Macro Regime Gate — yield curve / credit spread / VIX percentile / SPX breadth indicator 기반 결정적 regime 분류.

## 패키지 구조

```
domains/macro/
  __init__.py
  _boundary.py             # FRED + Yahoo (breadth fetch) + 경로 + env
  AGENTS.md                # (→ AGENTS.md symlink, gitignored)
  .guidelines/             # 6 markdown
  domain/
    regime.py              # IndicatorResult / RegimeResult (frozen)
  signals/                 # Signal 플러그인 (fetch + vote) — vote-in-signal
    base.py                # Signal ABC (fetch + vote) + empty_indicator
    registry.py            # @register_signal + SIGNALS dict
    factory.py             # build_signals(cfg) — config signals: → 인스턴스 (등록 트리거)
    _stats.py              # percentile helper (VIX)
    yield_curve.py / credit_spread.py / vix.py / breadth.py  # 4 Signal
  application/
    regime_classify.py     # classify_regime (registry vote 조회 + max-severity) + detect_regime_shift
  audit/                   # citation + log + violation (universe pattern mirror)
  config/
    regimes.yaml           # signals: 리스트 + 임계값 + cash_band + regime_shift_alert
  breadth_fetch.py         # Stage 0a — SPX breadth auto-fetch (Yahoo prefetch)
  spx_constituents_refresh.py  # SPX 구성종목 cache refresh
  main.py                  # Stage 0 CLI
```

## 4 Signal 목록

| name | source | value_label | vote |
|---|---|---|---|
| `yield_curve` | FRED DGS10 - DGS2 | inverted / flat / steepening / steep | spread ≤ crisis_signal → crisis; ≤ late_cycle_signal → late_cycle; else mid_cycle |
| `credit_spread` | FRED BAMLH0A0HYM2 | tight / moderate / stress / crisis | OAS ≥ crisis_min → crisis; ≥ late_cycle_min → late_cycle; ≤ mid_cycle_max → mid_cycle |
| `vix` | FRED VIXCLS + 5y history → percentile | panic / elevated / normal / complacent | percentile ≥ panic_min → crisis; ≤ complacent_max → late_cycle |
| `breadth` | breadth.yaml (Stage 0a prefetch) | weak / soft / neutral / broad | pct ≤ crisis_max → crisis; ≤ late_cycle_max → late_cycle; ≥ healthy_min → mid_cycle |

## 외부 연결점

| 방향 | 인터페이스 | 위치 |
|---|---|---|
| 입력 (config) | `config/regimes.yaml` | self-contained |
| 입력 (env) | `FRED_API_KEY` | `.env` via `_boundary.load_env()` |
| 입력 (breadth) | `$EXTERNAL_SIGNALS_MACRO_BREADTH_PATH` (Stage 0a 산출) | `_boundary.load_breadth_signal()` |
| 입력 (SPX 종목) | Wikipedia S&P 500 (HTML, stdlib) | `spx_constituents_refresh.fetch_constituents()` |
| 출력 (Stage 0) | `$TRAIL_TODAY/00-macro-regime.json` (schema `investment-stage0-macro-regime-v1`) | `_boundary.resolve_trail_dir` |
| 출력 (Stage 0a) | `$EXTERNAL_SIGNALS_MACRO_BREADTH_PATH` (yaml) + `$AUDIT_DIR/macro-breadth-{date}.json` | `_boundary.write_output_safely` |
| 출력 (SPX cache) | `infrastructure/_common/_spx_constituents.json` | `_boundary.resolve_path("infra_common")` |
| 출력 (audit) | `$AUDIT_DIR/macro-violations/{date}.jsonl` | append-only |

## DDD 규약

- 다른 macro 모듈은 `infrastructure.*` / utils path helper / `os.environ` 직접 사용 금지 → `_boundary.py` 통과
- `domains._shared.*` 는 예외 (AsOfClock / KRX calendar)
- 다른 도메인 (`domains.screener`, `domains.universe`) import 금지
- 새 indicator 추가 = `signals/{name}.py` (`@register_signal` Signal) + `factory.py` import + `config/regimes.yaml` `signals:` 한 줄

## 검증 명령

```bash
# DDD boundary 위반
grep -rn "from infrastructure\|import infrastructure" domains/macro/ --include="*.py" | grep -v _boundary.py
# 결과 0 줄

# 다른 도메인 import 검사
grep -rn "from domains\." domains/macro/ --include="*.py" | grep -v "domains.macro\|domains._shared"
# 결과 0 줄
```
