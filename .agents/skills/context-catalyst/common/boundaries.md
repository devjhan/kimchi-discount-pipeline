# Boundary — 외부 연결점 단일 게이트

## 핵심 규칙

catalyst 의 다른 모듈이 외부 자원 (infrastructure / os.environ / 다른 도메인) 에 직접 접근하면 boundary 우회. 모든 외부 호출은 `_boundary.py` 의 위임 함수만 사용.

예외 — `domains._shared.*` 는 직접 import 가능 (thin shared kernel). `infrastructure.*` 직접 import 예외는 **없음**.

## 검증

```bash
grep -rn "from infrastructure\|import infrastructure" domains/catalyst/ --include="*.py" | grep -v _boundary.py
# 결과 0 줄
```

추가: `test_catalyst_golden.py` 가 detector 산출의 byte-parity golden snapshot 회귀를 강제.

## 현재 export 함수

### Path / time / citation
- `resolve_path(alias, *, date=None) -> Path`
- `resolve_trail_dir(date=None)` / `now_kst()` / `now_iso_kst()`
- `normalize_to_trading_day(date)` / `is_trading_day(target)`
- `format_citation(source, ts, value)` — G7 `{SOURCE}@{ISO_KST}={VALUE}`

### Env / secret
- `load_env(path=None) -> dict[str, str]`
- `secret_safe_log(msg, env) -> str`

### Output
- `write_output_safely(out_path, payload) -> Path` — G20 collision-safe
- `base_report_envelope(...)` — D-Q-2
- `emit_summary(stage, summary, out_path)` — D-Q-6 handoff
- `resolve_allow_yahoo_fallback(cli_value)`

### Config loaders
- `load_detectors_config()` / `config_path(filename)`

### DART API
- 예외: `DartUnavailable`
- 함수: `dart_has_key`, `dart_iter_disclosures`

### KIS API
- 예외: `KisUnavailable`
- 함수: `kis_has_keys`, `kis_issue_access_token`, `kis_fetch_daily_ohlcv`

### Yahoo API
- 예외: `YahooUnavailable`
- 함수: `yahoo_krx_to_yahoo`, `yahoo_fetch_daily_ohlcv`

## 절대 금지

```python
from infrastructure.dart import client                    # ❌ boundary 우회
import os; os.environ.get("DART_API_KEY")                  # ❌
from domains.universe.domain.entry import UniverseEntry    # ❌ 다른 도메인
from domains.catalyst import _boundary                     # ✅
from domains._shared.time.clock import AsOfClock            # ✅ 예외
```
