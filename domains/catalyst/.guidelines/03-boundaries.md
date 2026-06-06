# Boundary — 외부 연결점 단일 게이트

## 핵심 규칙

catalyst 의 다른 모듈이 외부 자원 (infrastructure / os.environ / 다른 도메인) 에 직접
접근하면 boundary 우회. 모든 외부 호출은 `_boundary.py` 의 위임 함수만 사용.

예외 — `domains._shared.*` 는 직접 import 가능 (thin shared kernel — clock / calendar /
ports / adapters(disclosure_scan) / nav_history / audit). `infrastructure.*` 직접 import
예외는 **없음** (그 gate 는 절대적).

## 검증

```bash
# 결과 0 줄이어야 함 (_boundary.py 만 infrastructure import)
grep -rn "from infrastructure\|import infrastructure" domains/catalyst/ --include="*.py" | grep -v _boundary.py
```

추가: `domains/catalyst/tests/unit/test_catalyst_golden.py` 가 detector 산출의 byte-parity
golden snapshot 회귀를 강제 (`fixtures/golden_03_catalyst_events.json`).

## 현재 export 함수

### Path / time / citation
- `resolve_path(alias, *, date=None) -> Path` (alias: `operations_audit` / `trail_today` / `nav_cache` / `kis_token`)
- `resolve_trail_dir(date=None) -> Path`
- `now_kst() -> datetime`, `now_iso_kst() -> str`
- `normalize_to_trading_day(date) -> str`, `is_trading_day(target) -> bool`
- `format_citation(source, ts, value) -> str` — G7 `{SOURCE}@{ISO_KST}={VALUE}`

### Env / secret
- `load_env(path=None) -> dict[str, str]`
- `secret_safe_log(msg, env) -> str`

### Output
- `write_output_safely(out_path, payload) -> Path` — G20 collision-safe
- `base_report_envelope(*, schema, date, config_path, config_version, extra=None) -> dict` — D-Q-2
- `emit_summary(stage, summary, out_path) -> None` — D-Q-6 handoff
- `resolve_allow_yahoo_fallback(cli_value) -> bool`

### Config loaders (catalyst config/ 한정)
- `load_detectors_config() -> dict` — `config/detectors.yaml`
- `config_path(filename) -> Path` — `/` · `..` 거부 (basename only)

### DART API
- 예외: `DartUnavailable` (re-export)
- 함수: `dart_has_key(env)`, `dart_iter_disclosures(api_key, *, bgn_de, end_de, pblntf_ty=None, corp_code=None)`

### KIS API
- 예외: `KisUnavailable` (re-export)
- 함수: `kis_has_keys(env)`, `kis_issue_access_token(env, cache_path=None)`,
  `kis_fetch_daily_ohlcv(*, token, app_key, app_secret, stock_code, period_days=100, end_date=None, adjusted=True)`

### Yahoo API
- 예외: `YahooUnavailable` (re-export)
- 함수: `yahoo_krx_to_yahoo(stock_code, market="KOSPI")`, `yahoo_fetch_daily_ohlcv(ticker, period_days=750)`

(re-export 상수: `KST`)

## 새 외부 의존 추가 절차

1. `infrastructure/` 에 client 추가 (필요시)
2. `_boundary.py` 에 위임 함수 등록 (`{vendor}_{action}` naming)
3. 본 파일 export 표 갱신 + 패키지 `AGENTS.md` 외부 연결점 표 갱신
4. caller (`detectors/` / `io/` / `application/` / `main.py`) 가 `_boundary` 통해서만 호출

## 절대 금지

```python
# ❌ infrastructure 직접 import (boundary 우회)
from infrastructure.dart import client

# ❌ os.environ 직접 read
import os; os.environ.get("DART_API_KEY")

# ❌ 다른 도메인 내부 객체 import
from domains.universe.domain.entry import UniverseEntry   # Stage 1 산출물은 JSON 으로만 read

# ✅ 올바름
from domains.catalyst import _boundary
env = _boundary.load_env()
_boundary.dart_iter_disclosures(env["DART_API_KEY"], bgn_de=..., end_de=..., pblntf_ty="B")

# ✅ _shared 예외 — pure value / utility / shared adapter
from domains._shared.time.clock import AsOfClock
from domains._shared.adapters.disclosure_scan import scan_disclosures
```

catalyst 는 외부에 `03-catalyst-events.json` (산출) + stdout handoff 만 노출. 내부 객체
(`CatalystEvent` / `DetectContext` 등) 는 외부에서 import 금지 — downstream (Stage 4) 은
산출 파일 + envelope schema 만 인용.

## 의도된 비대칭 (`_shared` vs `_boundary`)

`_shared/` 는 *행동 없는 pure value/utility + 공유 스캔 스켈레톤* 만 호스팅. vendor IO
(DART/KIS/Yahoo) 가 다른 도메인과 겹쳐도 `_shared` 로 이전하지 않고 각 도메인 `_boundary.py`
에 동일 re-export 복제 — anti-corruption 경계 보존. `disclosure_scan` 이 `_shared` 에 있는
이유는 *알고리즘 (per-item 매칭/dedup) 공유* 이지 IO 공유가 아니며, 실제 DART 호출은
주입된 `DisclosureSourcePort` (= 각 도메인 `_boundary.dart_iter_disclosures`) 가 수행.
