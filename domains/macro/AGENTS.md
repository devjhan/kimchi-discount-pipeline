# domains/macro — Stage 0 Macro Regime Bounded Context

투자 파이프라인 Stage 0 (Macro Regime Gate) — yield curve / credit spread /
VIX percentile / SPX breadth indicator 기반 결정적 regime 분류. universe /
screener 와 isomorphic 한 DDD 구조. 각 indicator 는 ``Signal`` 플러그인 (fetch +
vote 캡슐화, ``@register_signal``); ``classify_regime`` 은 registry 로 vote 를
조회해 max-severity 만 aggregate (F-9 — screener Rule 패턴의 vote-in-signal).
voting aggregation 은 단일 함수 (VotingStrategy ABC 미도입 — over-abstraction 경계).

## 패키지 구조

```
domains/macro/
  __init__.py
  _boundary.py             # FRED + Yahoo (breadth fetch) + 경로(path helper) + env
  AGENTS.md                # (CLAUDE.md → AGENTS.md symlink, gitignored)
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
  spx_constituents_refresh.py  # SPX 구성종목 cache refresh (Wikipedia, breadth_fetch 가 read)
  main.py                  # Stage 0 CLI
```

새 indicator 추가 = `signals/{name}.py` (`@register_signal` Signal) + `factory.py`
import 한 줄 + `config/regimes.yaml` `signals:` 한 줄. `main` / `classify_regime` 수술 불요.

## 외부 연결점

| 방향 | 인터페이스 | 위치 |
|---|---|---|
| 입력 (config) | `config/regimes.yaml` | self-contained |
| 입력 (env) | `FRED_API_KEY` | `.env` via `_boundary.load_env()` |
| 입력 (breadth) | `$EXTERNAL_SIGNALS_MACRO_BREADTH_PATH` (Stage 0a 산출) | `_boundary.load_breadth_signal()` |
| 입력 (SPX 종목) | Wikipedia "List of S&P 500 companies" (HTML, urllib/stdlib) | `spx_constituents_refresh.fetch_constituents()` |
| 출력 (Stage 0) | `$TRAIL_TODAY/00-macro-regime.json` (schema `investment-stage0-macro-regime-v1`) | `_boundary.resolve_trail_dir` |
| 출력 (Stage 0a) | `$EXTERNAL_SIGNALS_MACRO_BREADTH_PATH` (yaml) + `$AUDIT_DIR/macro-breadth-{date}.json` | `_boundary.write_output_safely` |
| 출력 (SPX cache) | `infrastructure/_common/_spx_constituents.json` (breadth_fetch 가 read) | `_boundary.resolve_path("infra_common")` |
| 출력 (audit) | `$AUDIT_DIR/macro-violations/{date}.jsonl` | append-only |

## DDD bounded context 규약

- 다른 macro 모듈은 `infrastructure.*` / utils path helper / `os.environ` 직접 사용 금지 → `_boundary.py` 통과
- `domains._shared.*` 는 예외 (AsOfClock / KRX calendar)
- 다른 도메인 (`domains.screener`, `domains.universe`) import 금지
- 외부 의존 추가: `_boundary.py` + `AGENTS.md` + `.guidelines/03-boundaries.md` 동시 갱신

## 이전 이력

<!-- legacy-ok -->
- [Run 7 완료 2026-05-17] `domains.risk_engine.macro_regime` → `domains.macro.main` +
  `application.regime_classify` + `indicators`. 옛 파일 삭제.
- [Run 7 완료 2026-05-17] `domains.risk_engine.macro_breadth_fetch` →
  `domains.macro.breadth_fetch`. 옛 파일 삭제.
- [F-18 완료 2026-06-05] `domains.risk_engine.spx_constituents_refresh` →
  `domains.macro.spx_constituents_refresh` (breadth_fetch 의 SPX cache producer 가
  consumer 와 같은 BC 로). cache 경로(`infrastructure/_common/_spx_constituents.json`)
  무변경. risk_engine `_boundary.infra_common_dir()` 는 dead 가 되어 제거.
- thresholds.yaml 의 `macro:` 섹션 → `config/regimes.yaml` 로 완전 이전.
<!-- /legacy-ok -->

## 검증

```bash
# DDD boundary 위반
grep -rn "from infrastructure\|import infrastructure" domains/macro/ --include="*.py" | grep -v _boundary.py
# 결과 0 줄

# 다른 도메인 import 검사
grep -rn "from domains\." domains/macro/ --include="*.py" | grep -v "domains.macro\|domains._shared"
# 결과 0 줄
```
