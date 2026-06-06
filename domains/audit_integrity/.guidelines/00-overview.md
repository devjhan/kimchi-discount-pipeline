# audit_integrity — DDD Modular Monolith Overview

4-tier shadow portfolio (Index / Mechanical / LLM-Filtered / Random) 의 결정론 엔진 +
stat_tests. axiom #5 (통계적 정직성) 하에 시스템 LLM filter 의 부가가치를 검증한다. 매일 각
tier 의 NAV 를 **paper-trade** (실제 broker 호출 0 — G9) 하고, closed trade 를 tier 별 CSV 에
기록, 일별 NAV snapshot 누적, 분기 return 을 `quarterly_history` 로 roll-up 한다. pure
stat-tests 라이브러리 (`stat_tests.py`) 가 Welch t-test / bootstrap CI / self-disable trigger
평가를 제공. 구 LLM skill (`investment-audit-shadow-portfolio`) 에서 **F-6 으로 결정론 엔진
회수** — 모든 NAV/return 산술이 결정론 Python (ADR-0003 / G6).

## 4 Anchor (변경 시 도메인 안정성 영향)

1. **paper-trade only / 실제 체결 0 (G9)** — order/broker 코드 어디에도 없음. `_boundary` 는
   가격 read 함수만 노출 (`kis_fetch_daily_ohlcv` / `yahoo_fetch_daily_ohlcv`). 검증: grep
   `place_order|kis_order|TTTC080|order_cash|buy_order|sell_order` → 0 hit.
2. **stat-test 단일 source (G6 / ADR-0003)** — 모든 통계는 `stat_tests.py` (`welch_t_test` /
   `bootstrap_ci` / `quarterly_returns` / `evaluate_self_disable_trigger`) 에만. read-only skill 은
   결과를 *인용*, 재계산 금지.
3. **`_boundary.py` 단일 외부 게이트** — `_boundary.py` 외 `infrastructure` import 금지
   (불변식 C). **유일 예외: allowlist `init_shadow_state.py`** (top-level infra-import bootstrap
   스크립트, `tests/architecture/_helpers.py:BOUNDARY_C_ALLOWLIST`).
4. **G20 append-only state** — `init_shadow_state.py` 는 기존 state overwrite 거부
   (exit 2, `--force` 시 `.{N}.json`); 일배치 엔진은 `io/state_store.save_state` 로 atomic
   replace 하되 누적 `daily_snapshots` / `quarterly_history` 보존.

## 패키지 핵심 객체

### domain/state.py — value object (frozen + mutable 2)
- `TIER_KEYS = ("tier_0_passive_index", "tier_1_mechanical", "tier_2_llm_filtered", "tier_3_random")`
- `Holding` (frozen) — `ticker`/`qty`/`avg_cost_krw`/`weight`/`entry_date`
- `ClosedTrade` (frozen) — `tier`(CSV routing, body 제외)/`trade_id`/`ticker`/`entry_date`/
  `entry_price_krw`/`exit_date`/`exit_price_krw`/`return_pct`/`reason`
  (reason enum: `falsifier_triggered|30_day_holding_max|rebalance|catalyst_inactive`)
- `TierState` (mutable) — `name`/`initial_capital_krw`/`cash_krw`/`current_nav_krw`/
  `cumulative_return_pct`/`holdings`/`closed_trades`/`last_rebalance_date`/`quarterly_history`
- `ShadowPortfolioState` (mutable) — `schema`/`init_date`/`tiers`/`daily_snapshots`/`extra`

### domain/rules.py — pure 규칙
- `quarter_of` / `holding_age_days` / `select_top_k_catalyst_tickers` / `deterministic_random_k` /
  `max_weight_drift` / `trade_return_pct`

### application/run_daily_update.py — 4-tier 엔진 (I/O 0, 가격 주입)
- `EngineConfig` (frozen) — `top_k=5` / `max_hold_days=30` / `rebalance_threshold_pct=0.05` / `tier0_target_weight=0.5`
- `DailyInputs` (frozen) — tier 별 입력 (tier0_tickers / tier1_candidates+active_catalysts /
  tier2_recs+falsifier_triggered / tier3_pool)
- `UpdateResult` (mutable) — `state`/`closed_trades`/`warnings`/`citations`
- `run_daily_update(state, inputs, config, price_for) -> UpdateResult`

### stat_tests.py — pure 통계 (stdlib only) — `02-stat-tests.md`

### io/ — 외부 adapter (`_boundary` 경유)
- `price_source.py` `PriceSource` (KIS-first, Yahoo fallback close)
- `state_store.py` (load + atomic replace), `trade_log.py` (per-tier CSV append), `trail_loader.py`

### audit/ — citation + violation shim (`_shared` 재노출) — `04-audit.md`

### main.py / init_shadow_state.py — CLI
- `main`: `--date` / `--allow-yahoo-fallback` (`python -m domains.audit_integrity.main`)
- `init_shadow_state.py`: `--date` / `--config` / `--trail-dir` / `--force`

## 4 tier 구성

| key | name (default) | holdings 결정 |
|---|---|---|
| `tier_0_passive_index` | `"SPY+KOSPI200 50/50"` | `tier0_tickers` (default `US:SPY`,`KR:069500`) equal-weight 50/50, drift>threshold 시 rebalance |
| `tier_1_mechanical` | `"score-only top-K, no LLM"` | `03-catalyst-events.json` 의 top-K primary(a/b_type) — detector 출력 순서 = mechanical rank (score 필드 없음) |
| `tier_2_llm_filtered` | `"system actual recommendations"` | `05-sizing-recommendation.json` 의 `size_recommended`(+`_half_cap`) ticker, `size_pct_of_portfolio` weight |
| `tier_3_random` | `"random K from same A∩C universe"` | `01-universe ∩ 02-quality(pass)` pool 에서 date-hash seed (`sha256(date)`) 로 K 개 |

## 산출 / 외부 연결점

- `$AUDIT_DIR/shadow-portfolio-state.json` — accumulator (schema `investment-shadow-portfolio-state-v1`)
- `$AUDIT_DIR/trade-log-{tier}.csv` — tier 별 closed trade (header: `trade_id,ticker,entry_date,
  entry_price_krw,exit_date,exit_price_krw,return_pct,reason`)
- `$AUDIT_DIR/audit_integrity-violations/{date}.jsonl` — violation log (shim, 현재 parity-only)
- (read-only **outcome skill** 산출, 본 엔진 아님): `$AUDIT_DIR/outcome-{YYYY-Q}.md` /
  `$AUDIT_DIR/disable-trigger.json`
- handoff: `emit_summary` (STAGE_NAME `audit-shadow-portfolio` / init `audit-init-shadow-state`)
- 입력: `01-universe.json` / `02-quality-filter.json` / `03-catalyst-events.json` /
  `05-sizing-recommendation.json` / `05c-event-trigger-status` (`io/trail_loader`)

## exit

- `main.py`: 0 = success (state saved) 또는 Mode C (전 가격 source 미가용 → snapshot 미저장,
  state 보존); 2 = Mode B (state 파일 부재 → init 안내)
- `init_shadow_state.py`: 0 = template 작성; 2 = state 존재 & `--force` 없음

## init_shadow_state.py 특수 역할 (allowlist 근거)

one-shot composition-root / bootstrap 스크립트 — 초기 on-disk state envelope 를
`infrastructure._common.utils` (`base_report_envelope` / `write_output_safely` /
`emit_summary_line` / `load_yaml_config` / `audit_dir` / `normalize_to_trading_day` /
`DEFAULT_THRESHOLDS`) 에서 top-level 직접 구성해야 한다. top-level infra-import + composition-root
성격이라 `BOUNDARY_C_ALLOWLIST` 의 단일 entry — 불변식 C 가 flag 안 함.
