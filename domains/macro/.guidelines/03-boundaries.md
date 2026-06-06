# Boundary — 외부 연결점 단일 게이트

## 핵심 규칙

macro 의 다른 모듈이 외부 자원 (infrastructure / os.environ / 다른 도메인) 에 직접 접근하면 boundary 우회. 모든 외부 호출은 `_boundary.py` 의 위임 함수만 사용.

예외 — `domains._shared.*` 는 직접 import 가능.

## 검증

```bash
grep -rn "from infrastructure\|import infrastructure" domains/macro/ --include="*.py"
# _boundary.py 1 파일만

grep -rn "from domains\." domains/macro/ --include="*.py" | grep -v "domains.macro\|domains._shared"
# 결과 0 줄
```

## 현재 export 함수 (Run 7 시점)

### Path / time / citation
- `resolve_path(alias, *, date=None) -> Path`
- `now_kst()` / `now_iso_kst()`
- `is_trading_day(date)`, `normalize_to_trading_day(date)`
- `format_citation(source, ts, value)`

### Env / secret
- `load_env(path=None) -> dict`
- `secret_safe_log(msg, env) -> str`

### Output / envelope
- `write_output_safely(out_path, payload)`
- `resolve_trail_dir(date=None)`
- `base_report_envelope(...)`, `emit_summary(...)`

### Config
- `load_regimes_config()` — `config/regimes.yaml`
- `config_path(filename)` — basename 만 허용

### FRED API
- 예외: `FetchError`
- 함수: `fred_has_key`, `fred_latest`, `fred_series`, `fred_history_values`

### Yahoo Finance
- 예외: `YahooUnavailable`
- 함수: `yahoo_krx_to_yahoo`, `yahoo_fetch_daily_ohlcv`

### Breadth signal (Stage 0a output → Stage 0 input)
- `load_breadth_signal()` — `$EXTERNAL_SIGNALS_MACRO_BREADTH_PATH` read
