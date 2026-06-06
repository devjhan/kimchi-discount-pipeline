# Boundary — 외부 연결점 단일 게이트

## 핵심 규칙

screener 의 다른 모듈이 외부 자원 (infrastructure / os.environ / 다른 도메인) 에 직접 접근하면 boundary 우회. 모든 외부 호출은 `_boundary.py` 의 위임 함수만 사용.

## 검증

```bash
# 본 명령의 결과는 _boundary.py 1 파일만 등장해야 함
grep -rn "from infrastructure\|import infrastructure" domains/screener/

# os.environ / utils path helper 도 _boundary.py 만
grep -rn "os.environ\|_utils\." domains/screener/ | grep -v _boundary.py
```

CI 추가 시 본 검증을 자동화 후보.

## Ports & Adapters 패턴 (feature-first hexagonal — 전 BC 공통 템플릿)

> 본 절은 `_boundary.py` SPOF 해소 로드맵의 **공통 템플릿**이다. 다른 BC 의 boundary 가이드라인도 본 절을 참조한다.

`_boundary.py` 는 단일 게이트를 *유지*하되, fat god-facade (5~7 무관 concern bag → ISP 위반) 에서 **typed adapter factory** 로 진화한다. 외부 의존을 좁은 `typing.Protocol` **port** 로 선언하고, `_boundary` 가 concrete **adapter** 를 구성하며, composition root (`main.py`) 가 순수 use-case 에 주입한다.

```
Port (Protocol, 순수 typing)  →  domains/_shared/ports/<name>.py  (≥2 BC) 또는 domains/<bc>/ports/<name>.py (1 BC)
Adapter (impl, infra import)  →  _boundary.py 의 factory  xxx_adapter() -> XxxPort   (유일 infra-import 파일)
Composition root (주입)        →  main.py 가 _boundary.xxx_adapter() 구성 → run_xxx(..., port=...) 주입
Pure use-case (port 만 의존)   →  application/*.py  (infra / _boundary import 0)
```

**불변식 (parity gate):**
```bash
# application/ · domain/ 은 _boundary import 0 — port Protocol 에만 의존
grep -rn "import _boundary" domains/screener/application domains/screener/domain   # → 0
# _shared/ports 는 infra import 0 (D-CORE-4 안전 — domain 인접 배치 가능)
grep -rn "^from infrastructure\|^import infrastructure" domains/_shared/ports/      # → 0
```

**선례 (동형 패턴):** `domains/policy/ports/llm.py` (`PolicyEngine` Protocol) ← `policy/main.py` 가 `engine=` 주입; `infrastructure/llm/` (F-13 → D-CORE-7 evergreen 승격). 본 패턴은 그것을 fetch/output/citation/clock 축으로 일반화한 것.

**금지:** ① 게이트 *삭제* (D-CORE-4 강제 — `_boundary` 는 유일 infra-import 파일로 잔류). ② port 를 `domain/` 으로 옮긴 로직과 혼동 (port 는 Protocol = 순수 typing 만 domain 인접; adapter/impl 은 `_boundary` 잔류). ③ adapter 안에 수치/도메인 계산 (G6 — 변환만).

### Phase 0 적용 현황

| port | scope | adapter factory | 주입 경로 |
|---|---|---|---|
| `CitationPort` (`_shared/ports/citation.py`) | shared | `_boundary.citation_adapter()` | `main → run_screen → _refetch_into_cache → io/dart_adapter.{fetch_filings_for_ticker,detect_capital_signals_events}` |
| `ClockPort` (`_shared/ports/clock.py`) | shared | (형식화만 — `AsOfClock` 구조 매치) | wiring 후속 phase |

### Shared disclosure scan 미채택 (Wave5 / F-16) — 의도된 제외

`io/dart_adapter.detect_capital_signals_events` (B-type capital-signal lookback) 는 universe/catalyst 가 공유하는 `domains/_shared/adapters/disclosure_scan.scan_disclosures` 를 **채택하지 않는다**. 이유: ① dedup 부재 ② `_classify_signal` 다분기(keyword group 아님) ③ corp_code 조건부 stock_code 게이트 ④ rcept_dt 8자리 파싱 — 의미가 달라 공유 primitive 강제 시 행동 변경(dedup 추가 / 매칭 변경) = byte-parity 위반. 재무제표 fetch 와 함께 screener-지역 잔류. (catch #3 "3중복제" = catalyst 3 detector + universe; screener 는 5번째이나 형태 상이 → 통합 비용>이득.)

## 현재 export 함수 (PR3 시점)

### Path / time / citation
- `resolve_path(alias, *, date=None) -> Path` — 경로 alias → Path 단일 진입 (REPO_ROOT 기준, utils path helper 위임)
- `profiles_root() -> Path` — `governance/profiles` (ProfileRegistry root)
- `now_kst() -> datetime`, `now_iso_kst() -> str`
- `is_trading_day(date) -> bool` — KRX 거래일
- `format_citation(source, ts, value) -> str` — G7 형식 (free fn — back-compat)
- `citation_adapter() -> CitationPort` — CitationPort 어댑터 factory (주입용, `format_citation` 위임)

### Output
- `emit_summary(stage, summary, out_path)` — D-Q-6 handoff
- `write_envelope(out_path, payload, *, schema, date, ...)` — D-Q-2 envelope

### Config loader (screener 내부 config/ 한정)
- `load_profile(name)` / `load_strategy(name)` / `load_hard_guards()` / `load_methods_manifest()`
- `profile_path(name)` / `strategy_path(name)` — envelope `config_path` 인자용

### Env / secret
- `load_env(path=None) -> dict`
- `secret_safe_log(msg, env) -> str` — secret redact

### DART API (자체 HTTP 호출 금지)
- 상수: `DART_REPRT_CODE_ANNUAL`, `DART_FS_DIV_CONSOLIDATED` 등
- 예외: `DartUnavailable` (re-export)
- 함수: `dart_load_corp_index`, `dart_has_key`, `dart_fetch_financial_statements`, `dart_iter_disclosures`

## 새 외부 의존 추가 절차

1. `infrastructure/` 에 client 추가 (필요시)
2. `_boundary.py` 에 위임 함수 등록
3. 본 파일 (`05-boundaries.md`) 의 export 표 갱신
4. 패키지 `README.md` 외부 연결점 표 갱신
5. caller (`io/` 또는 `application/`) 가 `_boundary` 통해서만 호출

## 절대 금지

```python
# ❌ infrastructure 직접 import (boundary 우회)
from infrastructure.dart import client
client.fetch_financial_statements(...)

# ❌ os.environ 직접 read
import os
api_key = os.environ.get("DART_API_KEY")

# ❌ 다른 도메인 import
from domains.alpha_factory import universe

# ✅ 올바름
from domains.screener import _boundary
env = _boundary.load_env()
_boundary.dart_fetch_financial_statements(env["DART_API_KEY"], ...)
```

다른 도메인 import 금지는 DDD bounded context 의 핵심 — screener 는 외부에 `02-quality-filter.json` (산출) + stdout handoff 만 노출. 그 외 내부 객체 (TickerSnapshot, RuleResult 등) 는 외부에서 import 시도 금지.

## 예외 — `domains._shared.*` 직접 import 허용 (2026-05-17)

`domains/_shared/` 는 도메인 thin shared kernel — *행동 없는 pure value/utility* (AsOfClock / KRX calendar) 를 호스팅. screener 도 다음 모듈 직접 import:

```python
from domains._shared.time.clock import AsOfClock, KST, now_kst
from domains._shared.time.calendar import previous_trading_day, is_trading_day
```

`domains/screener/time/` 디렉토리는 2026-05-17 에 제거됨 — `_shared` 가 canonical single source. 기존 `from domains.screener.time.clock import AsOfClock` 형식의 import 는 더 이상 동작하지 않음 (의도된 변경). 회귀 검증: `domains/universe/tests/unit/test_universe_boundary.py::test_screener_time_package_removed`.

`_shared` 가 *유일한 예외*. `domains.universe`, `domains.alpha_factory`, `domains.audit_integrity` 등 다른 bounded context 의 객체는 여전히 import 금지.
