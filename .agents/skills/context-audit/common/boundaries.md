# Boundary — 외부 연결점 단일 게이트 (+ allowlist 1)

## 핵심 규칙

모든 외부 호출은 `_boundary.py` 위임 함수만. 예외 — `domains._shared.*` (audit) 직접 import 가능. **단, `infrastructure.*` 직접 import 의 유일 예외는 allowlist 된 `init_shadow_state.py`**.

## 두 불변식

| 불변식 | 내용 | 상태 |
|---|---|---|
| **C** | `infrastructure.*` 는 `_boundary.py` 만 import | 🟢 GREEN (allowlist 경유) |
| **D** | `application/` · `domain/` 이 `_boundary` 직접 import 안 함 | 🟢 GREEN (genuine — xfail 아님) |

**D GREEN**: 엔진이 가격 주입 (callback) 패턴 — Ports & Adapters 의 reference 사례.

## 현재 _boundary.py export

### 상수 / 예외
`KST` / `KisUnavailable` / `YahooUnavailable` (DartUnavailable 없음 — 가격만, DART 불요)

### Path / time / citation
`resolve_path(alias, *, date=None)` (alias: `operations_audit`/`trail_today`/`shadow_state`/`kis_token`) / `resolve_trail_dir(date=None)` / `now_kst()` / `now_iso_kst()` / `normalize_to_trading_day(date)` / `format_citation(source, ts, value)`

### Env / secret / config
`load_env(path=None)` / `secret_safe_log(msg, env)` / `load_thresholds()` / `thresholds_path()` / `resolve_allow_yahoo_fallback(cli_value)`

### Output emit
`write_output_safely(out_path, payload)` / `base_report_envelope(...)` / `emit_summary(stage, summary, out_path)`

### KIS / Yahoo 가격 (G9 read-only)
`kis_has_keys(env)` / `kis_issue_access_token(env, cache_path=None)` / `kis_fetch_daily_ohlcv(...)` / `yahoo_krx_to_yahoo(stock_code, market="KOSPI")` / `yahoo_fetch_daily_ohlcv(ticker, period_days=30)`

## init_shadow_state.py allowlist 상세

top-level `from infrastructure._common.utils import (...)`. one-shot bootstrap / composition-root → `BOUNDARY_C_ALLOWLIST` 단일 entry.

## 절대 금지 / 올바름

```python
# ❌ infrastructure 직접 import (init_shadow_state.py 외)
from infrastructure.kis import client

# ✅ 올바름 — 엔진은 가격을 주입받음 (D GREEN 유지의 핵심)
from domains.audit_integrity import _boundary
result = run_daily_update(state, inputs, config, price_for=price_source.close_on)

# ✅ _shared 예외
from domains._shared.audit.violation import GuardViolation
```

엔진(`application/`/`domain/`) 에 `_boundary` import 금지 — 가격은 `price_for` callback 으로 주입.

## 검증

```bash
grep -rn "from infrastructure\|import infrastructure" domains/audit_integrity/ --include="*.py" | grep -v _boundary.py
# → init_shadow_state.py 1줄 (allowlisted)
```
