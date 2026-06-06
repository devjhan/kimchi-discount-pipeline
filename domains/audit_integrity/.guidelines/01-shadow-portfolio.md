# Shadow Portfolio — 4-tier paper-trade 엔진

## 엔진 (`application/run_daily_update.py`)

```python
PriceFn = Callable[[str], tuple[float | None, str | None]]   # (price, citation)

def run_daily_update(state, inputs: DailyInputs, config: EngineConfig, price_for: PriceFn) -> UpdateResult
```

pure / I/O 0 — 가격은 `price_for` callback 으로 주입. 내부 helper `_Ctx` 가 가격 캐시 +
G7 citation + warning 수집. dispatch 순서: `_update_tier0` → `_update_slot_tier(tier_1)` →
`_update_tier2` → `_update_slot_tier(tier_3)` → `_record_snapshot_and_quarter`.

## tier 별 holdings 결정

- **tier_0** (`_update_tier0`): `tier0_tickers` equal-weight (`tier0_target_weight=0.5`). weight
  drift > `rebalance_threshold_pct` 면 전량 청산 (`reason="rebalance"`) 후 재진입. 첫날 → 진입.
- **tier_1** (`_update_slot_tier`, `active_catalysts=inputs.tier1_active_catalysts`): target =
  `select_top_k_catalyst_tickers(catalysts, top_k)`. holding 이 오늘 active catalyst 에 없고
  `age > max_hold_days` 면 청산 (`reason="catalyst_inactive"`). 빈 슬롯은 `nav/top_k` equal-weight.
- **tier_2** (`_update_tier2`): target = `tier2_recs` (ticker, size_pct). holding 이
  `tier2_falsifier_triggered` 에 들면 청산 (`reason="falsifier_triggered"`). 신규 진입 `nav*size_pct`.
- **tier_3** (`_update_slot_tier`, `active_catalysts=None`): target =
  `deterministic_random_k(tier3_pool, top_k, date)`. holding `age > max_hold_days` 면 청산
  (`reason="30_day_holding_max"`). 빈 슬롯 `nav/top_k`.
- 가격 미가용 ticker: 진입 보류 + warning (G8); 기존 holding 은 `avg_cost` fallback 으로 평가.

## paper-trade record (trade log)

`ClosedTrade` (`00-overview.md`) 를 `io/trade_log.append_closed_trades(trades) -> list[Path]` 이
`t.tier` 별 group → `$AUDIT_DIR/trade-log-{tier_key}.csv` append (새 파일 시 header).
`_HEADER = ("trade_id","ticker","entry_date","entry_price_krw","exit_date","exit_price_krw",
"return_pct","reason")`. `trade_id = f"{h.ticker}-{date}-{seq}"`.

## NAV / return tracking

`run_daily_update.py` primitive:
- `_nav(tier, ctx)` = `cash_krw + Σ ctx.value(h)`
- `_close` (ClosedTrade 기록, cash 반환, `closed_trades` 증가)
- `_open` (alloc 을 cash 로 clamp, `qty = alloc/price`, 진입 weight 0.0)
- `_finalize` (`current_nav_krw` 설정, `cumulative_return_pct = nav/initial - 1`, holding weight 재계산)
- `_record_snapshot_and_quarter` (`daily_snapshots[date] = {tier: nav}`; 분기 경계 crossing 시
  각 tier `quarterly_history` 에 `{"quarter": <YYYY-Qn>, "return_pct": nav_end/nav_start - 1}` append, dedup-guard)
- `trade_return_pct(entry, exit) = exit/entry - 1`

## PAPER-TRADE-ONLY 불변식 (G9)

order-placement 코드 없음. 유일한 외부 mutation 은 state/CSV 파일 쓰기 (paper). 모든 시장
접근은 `_boundary` 가격 read 함수만 (`kis_fetch_daily_ohlcv` / `yahoo_fetch_daily_ohlcv` /
`kis_issue_access_token` / `kis_has_keys`). `io/price_source.py` docstring: "G9: 시세 read only —
주문/매매 절대 금지". `state.py` docstring: "paper trade only (G9): qty/price 는 가상".
audit_integrity 는 account/order endpoint 를 **아예 건드리지 않음** (일봉 OHLCV 만) — G9c 의
order TR_ID 차단조차 도달 불필요.
