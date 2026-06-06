# Boundary — 외부 연결점 단일 게이트 (invariant-D 전환 완료)

## 핵심 규칙

risk_engine 의 다른 모듈이 `infrastructure.*` / `os.environ` 에 직접 접근하면 boundary 우회.
모든 외부 호출은 `_boundary.py` 위임 함수만 사용. 예외 — `domains._shared.*` (clock /
positions_store / ports / audit) 직접 import 가능.

## 두 불변식의 현재 상태

| 불변식 | 내용 | risk_engine 상태 |
|---|---|---|
| **C** | `infrastructure.*` 는 `_boundary.py` 만 import | 🟢 GREEN (leak grep 0) |
| **D** | `application/` · `domain/` 이 `_boundary` 직접 import 안 함 | 🟢 **GREEN (전환 완료 2026-06-06)** |

**D 전환 방식 (composition-root 주입):** 6개 `application/*.py` 는 더 이상 `_boundary` 를
import 하지 않는다. 각 모듈은 boundary 의존을 module-level placeholder + `configure(boundary)`
로 선언하고, 플랫 shim (`risk_engine/{sizing, falsifier_proximity, portfolio_state_derive,
thesis_sync, thesis_expiry_monitor, event_falsifier_linker}.py`) 이 **composition root** 로서
import 시 `_app_module.configure(_boundary)` 를 호출해 주입한다. `domain/` 은 원래부터 pure
(`thesis_projection.py` 는 `_shared.positions_store.schema` 만). `KisAccountPort` 는
`positions_sync.sync_account` 에 별도 주입 (G9c, 변경 없음).

> path-resolver seam (`_positions_dir` / `_trail_dir`) 은 application module-level 이름으로
> 유지 — e2e 테스트가 monkeypatch 하는 주입점이며 configure 가 production 값을 채운다.

근거 / 추적: **ADR-0005** + **D-ARCH-4**. fitness test
`tests/architecture/test_boundary_gate.py::test_application_domain_does_not_import_boundary[risk_engine]`
가 이제 hard-assert 로 통과 (`_D_UNCONVERTED` 비었음).

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

# ✅ 올바름 — composition root (플랫 shim) 에서만 _boundary 접근
# risk_engine/sizing.py (shim):
from domains.risk_engine import _boundary
from domains.risk_engine.application import sizing as _app_module
_app_module.configure(_boundary)        # application 에 주입

# ❌ application/ 에서 _boundary import (invariant-D 위반)
# from domains.risk_engine import _boundary   ← 금지. configure() 주입 이름만 사용.
```

## 전환 완료 (D → GREEN, 2026-06-06)

application 의 `_boundary` 직접 의존을 composition-root 주입으로 제거 완료. 각 application
모듈은 module-level placeholder + `configure(boundary)` 를 노출하고, 플랫 shim 이 import 시
`_boundary` 를 주입한다. `KisAccountPort` (G9c) 는 별도 typed-port 주입으로 유지. 추가
정제 여지: placeholder facade 주입을 concern 별 narrow port (clock/output/store) 로 세분화
(screener `CitationPort` 패턴) — 선택적 후속.
