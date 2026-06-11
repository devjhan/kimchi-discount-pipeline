# Boundary — 외부 연결점 단일 게이트

## 핵심 규칙

universe 의 다른 모듈이 외부 자원 (infrastructure / os.environ / 다른 도메인) 에 직접 접근하면 boundary 우회. 모든 외부 호출은 `_boundary.py` 의 위임 함수만 사용.

예외 — `domains._shared.*` 는 직접 import 가능 (AsOfClock / KRX calendar 등).

## 검증

```bash
grep -rn "from infrastructure\|import infrastructure" domains/universe/ --include="*.py"
# _boundary.py 1 파일만

grep -rn "os.environ\|_utils\." domains/universe/ --include="*.py" | grep -v _boundary.py

grep -rn "from domains\." domains/universe/ --include="*.py" | grep -v "domains.universe\|domains._shared"
```

## 현재 export 함수

### Path / time / citation
- `resolve_path(alias, *, date=None) -> Path`
- `now_kst()` / `now_iso_kst()`
- `is_trading_day(date)`, `format_citation(source, ts, value)`
- `resolve_trail_dir(date=None)`
- `resolve_allow_yahoo_fallback(cli_value)`

### Output
- `emit_summary(stage, summary, out_path)` — D-Q-6 handoff
- `base_report_envelope(...)` — D-Q-2 envelope
- `write_output_safely(out_path, payload)` — G20 collision-safe

### Config loaders
- `load_sources_config()` / `load_enrichers_config()` / `load_sub_config(filename)`
- `config_path(filename)`

### Env / secret
- `load_env(path=None) -> dict` / `secret_safe_log(msg, env) -> str`

### DART API
- 예외: `DartUnavailable`
- 함수: `dart_has_key`, `dart_load_corp_index`, `dart_iter_disclosures`, `dart_parse_subsidiary_table`, `dart_discover_preferred_pairs` 등

### KIS API
- 예외: `KisUnavailable`
- 함수: `kis_has_keys`, `kis_issue_access_token`, `kis_fetch_current_price`, `kis_fetch_daily_ohlcv`

### Yahoo API
- 예외: `YahooUnavailable`
- 함수: `yahoo_krx_to_yahoo`, `yahoo_fetch_daily_ohlcv`

## 절대 금지

```python
from infrastructure.dart import client            # ❌ boundary 우회
import os; os.environ.get("DART_API_KEY")          # ❌
from domains.screener.domain.verdict import ...    # ❌ 다른 도메인
from domains.universe import _boundary             # ✅
from domains._shared.time.clock import AsOfClock    # ✅ 예외
```
