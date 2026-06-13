# Boundary — 외부 연결점 단일 게이트 + Ports & Adapters

## 핵심 규칙

screener 의 다른 모듈이 외부 자원 (infrastructure / os.environ / 다른 도메인) 에 직접 접근하면 boundary 우회. 모든 외부 호출은 `_boundary.py` 의 위임 함수만 사용.

## 검증

```bash
grep -rn "from infrastructure\|import infrastructure" domains/screener/
# _boundary.py 1 파일만

grep -rn "os.environ\|_utils\." domains/screener/ | grep -v _boundary.py
```

## Ports & Adapters 패턴

`_boundary.py` 는 단일 게이트를 *유지*하되 fat god-facade 에서 **typed adapter factory** 로 진화.

```
Port (Protocol, 순수 typing)  →  domains/_shared/ports/<name>.py  (≥2 BC) 또는 domains/<bc>/ports/<name>.py (1 BC)
Adapter (impl, infra import)  →  _boundary.py 의 factory  xxx_adapter() -> XxxPort
Composition root (주입)        →  main.py 가 _boundary.xxx_adapter() 구성 → run_xxx(..., port=...) 주입
Pure use-case (port 만 의존)   →  application/*.py  (infra / _boundary import 0)
```

**불변식 (parity gate):**
```bash
grep -rn "import _boundary" domains/screener/application domains/screener/domain   # → 0
grep -rn "^from infrastructure\|^import infrastructure" domains/_shared/ports/      # → 0
```

### Phase 0 적용 현황

| port | scope | adapter factory | 주입 경로 |
|---|---|---|---|
| `CitationPort` (`_shared/ports/citation.py`) | shared | `_boundary.citation_adapter()` | `main → run_screen → _refetch_into_cache → io/dart_adapter` |
| `ClockPort` (`_shared/ports/clock.py`) | shared | (형식화만) | wiring 후속 |

## 현재 export 함수

### Path / time / citation
- `resolve_path(alias, *, date=None) -> Path`
- `profiles_root() -> Path` — `governance/policy/profiles`
- `now_kst()` / `now_iso_kst()`
- `is_trading_day(date)`, `format_citation(source, ts, value)`
- `citation_adapter() -> CitationPort`

### Output
- `emit_summary(stage, summary, out_path)`
- `write_envelope(out_path, payload, *, schema, date, ...)`

### Config loader
- `load_profile(name)` / `load_strategy(name)` / `load_hard_guards()` / `load_methods_manifest()`

### Env / secret
- `load_env(path=None) -> dict` / `secret_safe_log(msg, env) -> str`

### DART API
- 예외: `DartUnavailable`
- 상수: `DART_REPRT_CODE_ANNUAL`, `DART_FS_DIV_CONSOLIDATED`
- 함수: `dart_load_corp_index`, `dart_has_key`, `dart_fetch_financial_statements`, `dart_iter_disclosures`

## 예외 — `domains._shared.*` 직접 import 허용

`domains/_shared/` 는 thin shared kernel (AsOfClock / KRX calendar). `domains/screener/time/` 는 제거됨 (`_shared` 가 canonical single source).

## 절대 금지

```python
from infrastructure.dart import client                    # ❌ boundary 우회
import os; os.environ.get("DART_API_KEY")                  # ❌
from domains.alpha_factory import universe                # ❌
from domains.screener import _boundary                     # ✅
```
