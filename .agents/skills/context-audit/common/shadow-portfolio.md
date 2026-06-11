# Shadow Portfolio — 4-tier paper-trade 엔진

## 엔진 (`application/run_daily_update.py`)

```python
PriceFn = Callable[[str], tuple[float | None, str | None]]   # (price, citation)

def run_daily_update(state, inputs: DailyInputs, config: EngineConfig, price_for: PriceFn) -> UpdateResult
```

pure / I/O 0 — 가격은 `price_for` callback 으로 주입. dispatch 순서: tier0 → tier1 → tier2 → tier3 → snapshot.

## Tier 별 holdings 결정

- **tier_0**: `tier0_tickers` equal-weight (`tier0_target_weight=0.5`). drift > `rebalance_threshold_pct` 면 전량 청산 후 재진입.
- **tier_1**: target = `select_top_k_catalyst_tickers(catalysts, top_k)`. holding 이 active catalyst 에 없고 `age > max_hold_days` 면 청산 (`catalyst_inactive`).
- **tier_2**: target = `tier2_recs` (ticker, size_pct). holding 이 `tier2_falsifier_triggered` 에 들면 청산 (`falsifier_triggered`).
- **tier_3**: target = `deterministic_random_k(tier3_pool, top_k, date)`. holding `age > max_hold_days` 면 청산 (`30_day_holding_max`).
- 가격 미가용 ticker: 진입 보류 + warning (G8); 기존 holding 은 `avg_cost` fallback.

## Paper-trade record (trade log)

`ClosedTrade` — `tier`(CSV routing) / `trade_id` / `ticker` / `entry_date` / `entry_price_krw` / `exit_date` / `exit_price_krw` / `return_pct` / `reason` (enum: `falsifier_triggered|30_day_holding_max|rebalance|catalyst_inactive`). `io/trade_log.append_closed_trades(trades)` → `$AUDIT_DIR/trade-log-{tier_key}.csv`.

## NAV / return tracking

- `_nav(tier, ctx)` = cash + Σ value(holdings)
- `_close` → ClosedTrade 기록, cash 반환
- `_open` → alloc 을 cash 로 clamp, qty = alloc/price
- `_finalize` → `current_nav_krw`, `cumulative_return_pct`, holding weight 재계산
- `_record_snapshot_and_quarter` → `daily_snapshots[date]` + quarterly_history append (dedup-guard)

## PAPER-TRADE-ONLY 불변식 (G9)

order-placement 코드 없음. 유일한 외부 mutation = state/CSV 파일 쓰기 (paper). 모든 시장 접근은 `_boundary` 가격 read 함수만. audit_integrity 는 account/order endpoint 를 **아예 건드리지 않음** (일봉 OHLCV 만) — G9c 의 order TR_ID 차단조차 도달 불필요.
