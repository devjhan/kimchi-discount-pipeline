# Boundary — 외부 연결점 단일 게이트

## 핵심 규칙

universe 의 다른 모듈이 외부 자원 (infrastructure / os.environ / 다른 도메인) 에 직접 접근하면 boundary 우회. 모든 외부 호출은 `_boundary.py` 의 위임 함수만 사용.

예외 — `domains._shared.*` 는 직접 import 가능 (도메인 thin shared kernel — AsOfClock / KRX calendar 등 행동 없는 pure value/utility).

## 검증

```bash
# 본 명령의 결과는 _boundary.py 1 파일만 등장해야 함
grep -rn "from infrastructure\|import infrastructure" domains/universe/ --include="*.py"

# os.environ / utils path helper 도 _boundary.py 만
grep -rn "os.environ\|_utils\." domains/universe/ --include="*.py" | grep -v _boundary.py

# 다른 도메인 import 검사 (_shared 예외)
grep -rn "from domains\." domains/universe/ --include="*.py" | grep -v "domains.universe\|domains._shared"
```

자동 검증: `domains/universe/tests/unit/test_universe_boundary.py::test_boundary_no_infrastructure_import_outside_boundary` 와 `test_boundary_no_cross_domain_import_except_shared` 가 위 grep 을 subprocess 로 실행 → 결과 0 줄 강제.

## 현재 export 함수 (Run 6 시점)

### Path / time / citation
- `resolve_path(alias, *, date=None) -> Path` — 경로 alias → Path 단일 진입 (REPO_ROOT 기준, utils path helper 위임)
- `now_kst() -> datetime`, `now_iso_kst() -> str`
- `is_trading_day(date) -> bool` — KRX 거래일
- `format_citation(source, ts, value) -> str` — G7 형식
- `resolve_trail_dir(date=None) -> Path` — `$TRAIL_TODAY` resolver
- `resolve_allow_yahoo_fallback(cli_value) -> bool` — CLI / behavior.yaml 결정

### Output
- `emit_summary(stage, summary, out_path)` — D-Q-6 handoff stdout
- `base_report_envelope(*, schema, date, config_path, config_version, extra=None) -> dict` — D-Q-2 envelope
- `write_output_safely(out_path, payload) -> Path` — G20 collision-safe write

### Config loaders (universe 내부 config/ 한정)
- `load_sources_config()` — `config/sources.yaml`
- `load_enrichers_config()` — `config/enrichers.yaml`
- `load_sub_config(filename)` — `config/{filename}` (path traversal 차단)
- `config_path(filename) -> Path` — envelope `config_path` 인자 / 디버깅 용

### Env / secret
- `load_env(path=None) -> dict`
- `secret_safe_log(msg, env) -> str` — secret redact

### DART API
- 예외: `DartUnavailable` (re-export)
- 함수: `dart_has_key`, `dart_load_corp_index`, `dart_load_corp_full_index`, `dart_parse_subsidiary_table`, `dart_merge_with_manual_ssot`, `dart_iter_disclosures`, `dart_discover_preferred_pairs`, `dart_merge_preferred_pairs`

### KIS API
- 예외: `KisUnavailable` (re-export)
- 함수: `kis_has_keys`, `kis_issue_access_token`, `kis_fetch_current_price`, `kis_fetch_daily_ohlcv`

### Yahoo Finance API
- 예외: `YahooUnavailable` (re-export)
- 함수: `yahoo_krx_to_yahoo`, `yahoo_fetch_daily_ohlcv`

## 새 외부 의존 추가 절차

1. `infrastructure/` 에 client 추가 (필요시)
2. `_boundary.py` 에 위임 함수 등록 (`{vendor}_{action}` naming convention)
3. 본 파일 (`03-boundaries.md`) 의 export 표 갱신
4. 패키지 `README.md` 외부 연결점 표 갱신
5. caller (`sources/` 또는 `enrichers/` 또는 `application/`) 가 `_boundary` 통해서만 호출

## 절대 금지

```python
# ❌ infrastructure 직접 import (boundary 우회)
from infrastructure.dart import client
client.iter_disclosures(...)

# ❌ os.environ 직접 read
import os
api_key = os.environ.get("DART_API_KEY")

# ❌ 다른 도메인 import (screener / alpha_factory 등)
from domains.screener.io.financial_cache import LiveFinancialCache

# ✅ 올바름
from domains.universe import _boundary
env = _boundary.load_env()
_boundary.dart_iter_disclosures(env["DART_API_KEY"], ...)

# ✅ _shared 예외 — pure value/utility 만
from domains._shared.time.clock import AsOfClock
from domains._shared.time.calendar import previous_trading_day
```

다른 도메인 import 금지는 DDD bounded context 의 핵심 — universe 는 외부에
`01-universe.json` (산출) + stdout handoff 만 노출. 그 외 내부 객체 (UniverseEntry,
EnrichedEntry, Enricher 등) 는 외부에서 import 시도 금지.

## 의도된 한 가지 비대칭

`_shared/` 모듈은 *행동 없는 pure value/utility* 만 호스팅. 만약 KIS / DART / Yahoo
helper 가 두 도메인에서 동시 사용된다면 (예: macro 가 KIS 가 필요해진 미래),
**`_shared` 로 이전하지 않고** 각 도메인의 `_boundary.py` 에 동일 re-export 를
복제. 근거: `_shared` 는 도메인 간 *공유 객체 ID 일관성* 이 필요한 케이스에만
사용 (AsOfClock 의 `is` 비교 등). 외부 IO 는 도메인별 ACL 통과해야 anti-corruption
원칙 보존.
