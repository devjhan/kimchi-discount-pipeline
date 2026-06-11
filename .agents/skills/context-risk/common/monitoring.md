# Monitoring — 5a/5b/5c/5d + account sync + state derive

모든 monitor 는 **alert only — 매매 명령 절대 발행 안 함 (G9)**.

## positions store (cross-day state)

`domains/_shared/positions_store/store.py:PositionsStore` (`_boundary.positions_store()` 통해서만 접근):

```python
load_open_raw(*, category=None) -> (list[dict], list[str])
load_open(*, category=None) -> (list[PositionThesis], list[str])
load_one(ticker) -> PositionThesis | None;  has_open_thesis(ticker) -> bool
commit(thesis, *, writer) -> Path
thesis_path(ticker) -> Path
```

`PositionThesis` (공유 schema, frozen): `ticker` / `name` / `falsifier: FalsifierSpec` / `entry_date` / `time_horizon_months` / `edge_source` / `entry_price_krw` / `status` / `entry_catalyst` / `asymmetry_score` / `provenance`. `FalsifierSpec.category` ∈ `("time_cap", "metric_trigger", "event_trigger")`.

## positions_sync (계좌 read-only 동기화)

`sync_account(*, date, env, account: KisAccountPort) -> AccountSummary` — KIS read 6 endpoint 호출. policy disabled 또는 KIS env 부재 시 graceful skip. `KisAutoTradeBlocked` 는 re-raise (exit 2). 산출: `_summary-{date}.json` + per-ticker `balance-{date}.json`.

## portfolio_state_derive (파생 상태)

`derive_state(*, positions_dir, date, lookback_days=365) -> DerivedState` — `_summary-{date}.json` scan → peak / current → `compute_drawdown_pct` / `compute_cash_pct`. 산출 `_derived-{date}.json` 이 sizing drawdown brake 를 먹임.

## 5a thesis_sync (projection)

Stage 4 accepted **new_entry** candidate 를 `thesis.json` position record 로 결정론 projection. `verdict=="accepted"` AND `thesis_kind=="new_entry"` 만; **idempotent** (thesis_path 존재 시 skip). multi-falsifier 는 primary 만.

## 5b falsifier_proximity

보유 포지션의 falsifier **근접도** 측정. `falsifier.category` 별 분기:
- `time_cap`: 경과/horizon → distance ratio
- `metric_trigger`: v1 은 price-only (market_snapshot 없으면 unmeasurable)
- `event_trigger`: 항상 unmeasurable (5c / ingest 로 위임)

`render_drift_md` → `{ticker_dir}/drift-{date}.md`. G6 결정론, G9 alert-only.

## 5c event_falsifier_linker

event-trigger falsifier 의 **발동 여부** 를 Stage 3 catalyst 와 cross-reference. store `category="event_trigger"` 필터, `03-catalyst-events.json` index, presence/absence × seen_today → triggered/not_triggered/unspecified. G6/G7/G8/G9.

## 5d thesis_expiry

time-horizon **expiry tier** 계산. tier: `notice` (90일 전) / `warn` (30일 전) / `expired` (0) / `overdue` (-30) / ok / unmeasurable. `needs_user_decision` = expired|overdue|warn. `render_expiry_md` → `{ticker_dir}/expiry-{date}.md`.

## Drawdown circuit breaker

탐지: `portfolio_state_derive` (`current_drawdown_pct`). brake 적용: sizing (`drawdown_brake_active = current_drawdown_pct >= threshold_pct` → `size_one` 절반; G17).
