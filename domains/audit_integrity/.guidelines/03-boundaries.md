# Boundary — 외부 연결점 단일 게이트 (+ allowlist 1)

## 핵심 규칙

audit_integrity 의 다른 모듈이 `infrastructure.*` / `os.environ` 에 직접 접근하면 boundary
우회. 모든 외부 호출은 `_boundary.py` 위임 함수만. 예외 — `domains._shared.*` (audit) 직접
import 가능. **단, `infrastructure.*` 직접 import 의 유일 예외는 allowlist 된
`init_shadow_state.py`** (아래).

## 두 불변식의 현재 상태

| 불변식 | 내용 | audit_integrity 상태 |
|---|---|---|
| **C** | `infrastructure.*` 는 `_boundary.py` 만 import | 🟢 GREEN (allowlist 경유) |
| **D** | `application/` · `domain/` 이 `_boundary` 직접 import 안 함 | 🟢 **GREEN (genuine — xfail 아님)** |

**C — allowlist 경유 GREEN:** `grep "from infrastructure" domains/audit_integrity/ --include="*.py"
| grep -v _boundary.py` 는 정확히 1줄 — `init_shadow_state.py:21` (allowlisted).
`test_only_boundary_imports_infrastructure[audit_integrity]` 는 hard-assert 이며 allowlist skip
(`test_boundary_gate.py:30`) 로 통과.

**D — genuine GREEN:** `grep "_boundary" domains/audit_integrity/application/ domains/audit_integrity/
domain/` → 0. application/domain 은 `_boundary` 의존 없음 (엔진은 `price_for` callback 으로 가격
주입, serde 는 pure). `_D_UNCONVERTED` 는 비었고 (전 BC 전환 완료 2026-06-06)
`test_application_domain_does_not_import_boundary[audit_integrity]` 는 hard-assert 로 pass.
`_boundary` 를 import 하는 파일은 모두 허용 레이어 (`io/` + `main.py` + `audit/log.py`).

> 이 BC 는 처음부터 (다른 BC 의 후속 전환과 달리) D 가 green 이었다 — 엔진이 가격 주입
> (callback) 패턴으로 작성됐기 때문 — Ports & Adapters 의 reference 사례.

## 검증

```bash
grep -rn "from infrastructure\|import infrastructure" domains/audit_integrity/ --include="*.py" | grep -v _boundary.py
# → init_shadow_state.py 1줄 (allowlisted)
# G9: KIS order TR_ID / broker write 부재 (price read endpoint 만)
```

## 현재 export 함수 (`_boundary.py`)

### 상수 / 예외 re-export
- `KST` / `KisUnavailable` / `YahooUnavailable` (**DartUnavailable 없음** — 가격만 필요, DART 불요)

### Path / time / citation
- `resolve_path(alias, *, date=None)` (alias: `operations_audit` / `trail_today` / `shadow_state` / `kis_token`)
- `resolve_trail_dir(date=None)`, `now_kst()`, `now_iso_kst()`, `normalize_to_trading_day(date)`,
  `format_citation(source, ts, value)`

### Env / secret / config
- `load_env(path=None)`, `secret_safe_log(msg, env)`, `load_thresholds()`, `thresholds_path()`,
  `resolve_allow_yahoo_fallback(cli_value)`

### Output emit
- `write_output_safely(out_path, payload)` (G20 `.{N}.json`),
  `base_report_envelope(*, schema, date, config_path, config_version, extra=None)`,
  `emit_summary(stage, summary, out_path)`

### KIS / Yahoo 가격 (G9 read-only)
- `kis_has_keys(env)`, `kis_issue_access_token(env, cache_path=None)`,
  `kis_fetch_daily_ohlcv(*, token, app_key, app_secret, stock_code, period_days=20, end_date=None, adjusted=True)`
- `yahoo_krx_to_yahoo(stock_code, market="KOSPI")`, `yahoo_fetch_daily_ohlcv(ticker, period_days=30)`

## init_shadow_state.py allowlist 상세

top-level 에서 `from infrastructure._common.utils import (audit_dir as _audit_dir,
DEFAULT_THRESHOLDS, base_report_envelope, emit_summary_line, load_yaml_config,
normalize_to_trading_day, write_output_safely)`. one-shot bootstrap / composition-root 스크립트라
exempt — `BOUNDARY_C_ALLOWLIST` 의 단일 entry. 4 빈 tier 를 `_empty_tier(name,
initial_capital_krw)` 로 구성해 초기 state envelope 작성.

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

엔진 (`application/`/`domain/`) 에 `_boundary` 를 import 하지 말 것 — 가격은 `price_for`
callback 으로 주입해야 D 불변식 GREEN 유지.
