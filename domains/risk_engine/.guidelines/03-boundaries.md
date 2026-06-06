# Boundary — 외부 연결점 단일 게이트 + 미전환 잔여

## 핵심 규칙

risk_engine 의 다른 모듈이 `infrastructure.*` / `os.environ` 에 직접 접근하면 boundary 우회.
모든 외부 호출은 `_boundary.py` 위임 함수만 사용. 예외 — `domains._shared.*` (clock /
positions_store / ports / audit) 직접 import 가능.

## 두 불변식의 현재 상태 (중요)

| 불변식 | 내용 | risk_engine 상태 |
|---|---|---|
| **C** | `infrastructure.*` 는 `_boundary.py` 만 import | 🟢 GREEN (leak grep 0) |
| **D** | `application/` · `domain/` 이 `_boundary` 직접 import 안 함 | 🔴 **RED — 미전환** |

**D 가 RED 인 이유:** 6개 `application/*.py` 가 `_boundary` 를 직접 import 한다 (예:
`application/sizing.py:15`, `application/falsifier_proximity.py:18`, ...). `domain/` 은
pure (직접 import 없음 — `thesis_projection.py` 는 `_shared.positions_store.schema` 만).
Ports & Adapters 전환이 **미완료** — `KisAccountPort` 만 `positions_sync.sync_account` 에
주입되고, 나머지 path/time/output 관심사는 `_boundary` 로 직접 도달.

근거 / 추적: **ADR-0005** ("미전환 잔여: macro/policy/risk_engine 의 application·domain 이
아직 `_boundary` 직접 import") + **D-ARCH-4**. fitness test
`tests/architecture/test_boundary_gate.py` 가 risk_engine 을 `_D_UNCONVERTED` 의 `xfail(strict=False)`
로 추적 — port 주입 전환 시 자동 green 승격 (`governance/decisions/0005-boundary-ports-and-adapters.md`).

## 검증

```bash
grep -rn "from infrastructure\|import infrastructure" domains/risk_engine/ | grep -v _boundary.py   # → 0 (C GREEN)
# KisAccountPort surface = read 6 (order/submit/cancel 부재 — tests/unit/test_positions_sync.py 회귀)
```

## 현재 export 함수 (`_boundary.py`)

### 상수 re-export
- `KST` / `DEFAULT_THRESHOLDS` / `DEFAULT_ENV` / `FetchError`

### Path / time / citation
- `resolve_positions_dir()` (→ `positions_dir()`), `resolve_trail_dir(date=None)`
- `now_iso_kst()`, `now_kst()`, `format_citation(source, ts, value)`

### Output (re-export)
- `base_report_envelope`, `emit_summary_line`, `write_output_safely`

### Config / env (re-export)
- `load_env_file`, `load_yaml_config`, `load_user_portfolio`, `normalize_to_trading_day`,
  `secret_safe_log`

### Positions store seam (F-5b)
- `positions_store(root=None) -> PositionsStore`, `commit_thesis(thesis) -> Path`,
  `load_derived_state(date, *, positions_dir=None) -> dict | None`

### KIS read-only gateway (G9 — 6 endpoint, free-fn back-compat)
- `kis_read_only_enabled() -> (bool, str|None)` (G9b runtime-policy check)
- `kis_issue_access_token(env)`, `kis_fetch_account_balance(**)`, `kis_fetch_buyable_amount(**)`,
  `kis_fetch_account_assets(**)`, `kis_fetch_realized_pnl(**)`, `kis_fetch_sellable_qty(*, stock_code, **)`

### KisAccountPort adapter (G9c)
- `_KisAccountAdapter` (read 6 메서드) + `kis_account_adapter() -> KisAccountPort`

### re-export 예외
- `KisAutoTradeBlocked`, `KisUnavailable`, `FetchError`

vendor: **KIS 만** (DART / Yahoo / FRED 없음 — filing/market-data 는 macro/universe/catalyst).

## 절대 금지

```python
# ❌ infrastructure 직접 import
from infrastructure.kis import client

# ❌ os.environ 직접 read
import os; os.environ["KIS_APP_KEY"]

# ✅ 올바름
from domains.risk_engine import _boundary
account = _boundary.kis_account_adapter()   # read-only port (G9c)
store = _boundary.positions_store()
```

## 전환 시 (D → GREEN) 방향

application 의 `_boundary` 직접 의존을 typed port (clock/output/store port) 주입으로 치환,
composition root (각 flat shim `main`) 에서 adapter wire. `KisAccountPort` 가 reference
template. 전환 완료 시 `_D_UNCONVERTED` 에서 `risk_engine` 제거 → xfail 자동 green.
