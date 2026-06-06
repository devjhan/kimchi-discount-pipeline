# risk_engine — DDD Modular Monolith Overview

투자 파이프라인 Stage 5 (sizing) + Stage 5a~5d (monitoring) + KIS read-only account BC.
`SizeRecommendation` 산출 (fractional Kelly + cap) 과, 보유 포지션의 falsifier proximity /
event trigger / expiry tier 일일 monitoring, 그리고 계좌 read-only 동기화 / 파생 상태 계산을
담당한다. universe/screener 와 같은 DDD 레이어링 (`domain/` pure + `application/` orchestration)
을 따르되, **7개 flat CLI entry** + `ports/` + 공유 `positions_store` 의존이라는 점이 다르다.

## 4 Anchor (변경 시 도메인 안정성 영향)

1. **Kelly/sizing 산식 단일 source (G6)** — `domain/sizing.py:compute_fractional_kelly` +
   `size_one` + `apply_portfolio_kelly_cap`. pure, IO 0. 산식은 본 모듈에만 존재 —
   application / LLM skill 어디서도 재구현 금지.

2. **positions thesis store 단일 source (F-5b)** — `_boundary.positions_store()` 가 공유
   `domains._shared.positions_store.store.PositionsStore` 반환. 3 monitor + thesis_sync 가
   모두 `load_open_raw` / `commit` / `thesis_path` 로만 read/write.

3. **`_boundary.py` 단일 infra-import 게이트** — `infrastructure.*` 직접 import 는
   `_boundary.py` 만. 검증: `grep -rn "from infrastructure" domains/risk_engine/ | grep -v _boundary.py`
   → 0 줄 (GREEN). application/domain 의 `_boundary` 직접 import 도 제거 완료
   (composition-root `configure()` 주입, 2026-06-06) — invariant-D GREEN, `03-boundaries.md`.

4. **type-level read-only KIS gate (G9c, 4번째 구조적 guard)** —
   `ports/kis_account.py:KisAccountPort` 는 read 6 메서드만 노출 (order/submit/cancel 없음).
   매매 호출이 *type 으로 표현 불가*. composition root: `positions_sync.main` →
   `_boundary.kis_account_adapter()`.

(보조 anchor: 공유 clock `_boundary.now_iso_kst` / `now_kst` / `KST`.)

## 패키지 핵심 객체

### domain/ — pure rule (IO 0)
> 주의: risk_engine `domain/` value object 은 `@dataclass` (mutable — verdict/guard 변형).
> `frozen=True` 는 공유 `domains/_shared/positions_store/schema.py` (`PositionThesis` /
> `FalsifierSpec` / `ThesisProvenance`) 와 `store.py` (`PositionsStore`) 에만.

- `sizing.py` `SizeRecommendation` (`ticker`/`name`/`verdict`/`size_pct_of_portfolio`/`size_krw`/
  `size_inputs`/`rationale`/`guards_applied`/`rejection_reason`) + Kelly/asymmetry 산식
- `proximity.py` `ProximityRecord` (`proximity` low/medium/high/unmeasurable + `distance_ratio`) + band classify
- `expiry.py` `ExpiryRecord` (`tier` notice/warn/expired/overdue/unmeasurable) + classify_tier
- `event_trigger.py` `EventTriggerStatus` (`signal` triggered/not_triggered/unspecified) + build_stage3_index
- `portfolio_state.py` `DerivedState` (peak / drawdown% / cash%) + drawdown/cash 산식
- `thesis_projection.py` — stage4 → thesis.json schema-bridge projection (pure)

### ports/ — typed port
- `kis_account.py` `KisAccountPort` Protocol — G9c read-only 6 메서드

### application/ — orchestration + IO (`_boundary` 는 shim 이 configure() 주입 — invariant-D GREEN)
- `sizing.py` / `portfolio_state.py` / `thesis_sync.py` / `falsifier_proximity.py` /
  `event_falsifier_linker.py` / `thesis_expiry.py` — 각 stage main

### flat CLI shim (`python -m domains.risk_engine.<name>`)
- `sizing` (5) / `positions_sync` (계좌 — full logic, 위임 아님) / `portfolio_state_derive` /
  `thesis_sync` (5a) / `falsifier_proximity` (5b) / `event_falsifier_linker` (5c) /
  `thesis_expiry_monitor` (5d). `daily_pipeline.sh` 가 이 이름들을 hardcode → 이름 보존 (ADR-0007).

## 산출 / 외부 연결점

| stage | 출력 | schema |
|---|---|---|
| 5 sizing | `operations/{date}/05-sizing-recommendation.json` | `investment-stage5-sizing-v1` |
| positions_sync | `telemetry/positions/_summary-{date}.json` (+ per-ticker `{ticker_dir}/balance-{date}.json`) | `investment-positions-sync-v1` |
| portfolio_state_derive | `telemetry/positions/_derived-{date}.json` | `investment-portfolio-derived-v1` |
| 5a thesis_sync | `operations/{date}/05a-thesis-sync.json` (+ `{ticker_dir}/thesis.json`) | `investment-stage5a-thesis-sync-v1` |
| 5b falsifier_proximity | `operations/{date}/05b-falsifier-proximity.json` (+ `{ticker_dir}/drift-{date}.md`) | `investment-stage5b-falsifier-proximity-v1` |
| 5c event_falsifier_linker | `operations/{date}/event-trigger-status-{date}.json` | `investment-stage5c-event-falsifier-linker-v1` |
| 5d thesis_expiry | `operations/{date}/05d-thesis-expiry.json` (+ `{ticker_dir}/expiry-{date}.md`) | `investment-stage5d-thesis-expiry-v1` |

- `{ticker_dir}` = `ticker.replace(":","_").replace("/","_")` (예: `KR:003550` → `KR_003550`)
- 모든 JSON 은 `write_output_safely` (G20, 재실행 시 `.{N}.json`/`.{N}.md`) + `base_report_envelope`
- handoff: `emit_summary_line(STAGE_NAME, ...)` (STAGE_NAME: `stage5-sizing` / `positions-sync` /
  `portfolio-state-derive` / `stage5a-thesis-sync` / `stage5b-falsifier-proximity` /
  `stage5c-event-falsifier-linker` / `stage5d-thesis-expiry`)
- cross-day state: `telemetry/positions/` (`$POSITIONS_DIR`) — risk_engine 는 **stateful BC**

## CLI / exit

- 공통 flag: `--date` / `--trail-dir` / `--dry-run`; 일부 `--config` / `--env` / `--lookback-days`
  (stage 별 차이는 `01-sizing.md` / `02-monitoring.md`)
- exit 0 = success (graceful skip / G12 size-hold 포함). 유일 비0: `positions_sync.main`
  이 `KisAutoTradeBlocked` catch 시 **2 (FATAL, fail-loud — G9c, never graceful)**.

> tests 는 root `tests/` 에 위치 (pyproject testpaths 에 `domains/risk_engine/tests` 없음).
> 구조 결정 근거: ADR-0007 (concern 서브패키지 reorg 기각 — 물리 레이어만, concern 은 논리적).
