# Boundary — 외부 연결점 단일 게이트 (invariant-D 전환 완료)

## 핵심 규칙

모든 외부 호출은 `_boundary.py` 위임 함수만. 예외 — `domains._shared.*` (clock / positions_store / ports / audit) 직접 import 가능.

## 두 불변식

| 불변식 | 내용 | 상태 |
|---|---|---|
| **C** | `infrastructure.*` 는 `_boundary.py` 만 import | 🟢 GREEN (leak grep 0) |
| **D** | `application/` · `domain/` 이 `_boundary` 직접 import 안 함 | 🟢 **GREEN (전환 완료 2026-06-06)** |

**D 전환 방식**: 6개 `application/*.py` 는 module-level placeholder + `configure(boundary)` 선언. 플랫 shim 이 composition root 로서 import 시 `_app_module.configure(_boundary)` 호출. `KisAccountPort` 는 G9c 별도 typed-port 주입.

## 현재 _boundary.py export

### 상수 re-export
`KST` / `DEFAULT_THRESHOLDS` / `DEFAULT_ENV` / `FetchError`

### Path / time / citation
`resolve_positions_dir()` / `resolve_trail_dir(date=None)` / `now_iso_kst()` / `now_kst()` / `format_citation(source, ts, value)`

### Output
`base_report_envelope` / `emit_summary_line` / `write_output_safely`

### Config / env
`load_env_file` / `load_yaml_config` / `load_user_portfolio` / `normalize_to_trading_day` / `secret_safe_log`

### Positions store seam (F-5b)
`positions_store(root=None) -> PositionsStore` / `commit_thesis(thesis) -> Path` / `load_derived_state(date, *, positions_dir=None) -> dict | None`

### KIS read-only gateway (G9)
`kis_read_only_enabled() -> (bool, str|None)` / `kis_issue_access_token(env)` / `kis_fetch_account_balance(**)` / `kis_fetch_buyable_amount(**)` / `kis_fetch_account_assets(**)` / `kis_fetch_realized_pnl(**)` / `kis_fetch_sellable_qty(*, stock_code, **)`

### KisAccountPort adapter (G9c)
`_KisAccountAdapter` + `kis_account_adapter() -> KisAccountPort`

### 예외
`KisAutoTradeBlocked` / `KisUnavailable` / `FetchError`

Vendor: **KIS 만** (DART / Yahoo / FRED 없음).

## 절대 금지

```python
# ❌ infrastructure 직접 import
from infrastructure.kis import client

# ❌ os.environ 직접 read
import os; os.environ["KIS_APP_KEY"]

# ✅ 올바름 — composition root (플랫 shim) 에서만 _boundary 접근
from domains.risk_engine import _boundary
from domains.risk_engine.application import sizing as _app_module
_app_module.configure(_boundary)

# ❌ application/ 에서 _boundary import (invariant-D 위반)
# from domains.risk_engine import _boundary   ← 금지
```

## 검증

```bash
grep -rn "from infrastructure\|import infrastructure" domains/risk_engine/ | grep -v _boundary.py   # → 0
```
