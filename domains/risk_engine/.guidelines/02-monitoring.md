# Monitoring — 5a/5b/5c/5d + account sync + state derive

모든 monitor 는 **alert only — 매매 명령 절대 발행 안 함 (G9)**. 산식은 pure `domain/`,
orchestration + IO 는 `application/` (현재 `_boundary` 직접 — `03-boundaries.md`).

## positions store (cross-day state)

`domains/_shared/positions_store/store.py:PositionsStore` (`@dataclass(frozen=True)`,
`root: Path`), `_boundary.positions_store(root=None)` 통해서만 접근:

```python
load_open_raw(*, category=None) -> (list[dict], list[str])    # 정렬 iterdir, status!="open" skip, 손상 JSON → warning
load_open(*, category=None) -> (list[PositionThesis], list[str])
load_one(ticker) -> PositionThesis | None;  has_open_thesis(ticker) -> bool
commit(thesis, *, writer) -> Path            # writer 주입 (_boundary.commit_thesis → write_output_safely)
thesis_path(ticker) -> Path                  # root/{ticker_dir}/thesis.json
```

3 monitor loader (`load_open_positions` / `load_open_thesis` /
`load_event_trigger_positions`) 는 `load_open_raw` 의 thin wrapper.

`PositionThesis` (공유 schema, frozen): `ticker` / `name` / `falsifier: FalsifierSpec` /
`entry_date` / `time_horizon_months` / `edge_source` / `entry_price_krw` / `status` /
`entry_catalyst` / `asymmetry_score` / `provenance`. `FalsifierSpec.category` ∈
`("time_cap", "metric_trigger", "event_trigger")` (반증가능성 axiom — `__post_init__` 검증).

## positions_sync (계좌 read-only 동기화)

`positions_sync.py` (위임 아닌 full logic, `KisAccountPort` composition root).
`sync_account(*, date, env, account: KisAccountPort) -> AccountSummary` 가 KIS read 6
endpoint 호출 (`issue_access_token` / `fetch_account_balance` / `fetch_buyable_amount` /
`fetch_account_assets` / `fetch_realized_pnl` / `fetch_sellable_qty`). policy disabled 또는
KIS env 부재 시 graceful skip; `KisAutoTradeBlocked` 는 re-raise (절대 graceful 아님 — exit 2).
산출: `_summary-{date}.json` + per-ticker `balance-{date}.json`.

## portfolio_state_derive (파생 상태)

`portfolio_state_derive.py` → `application/portfolio_state.py`.
`derive_state(*, positions_dir, date, lookback_days=365) -> DerivedState` 가 lookback 범위
`_summary-{date}.json` scan → peak (전체 최대) / current (최근) → pure `compute_drawdown_pct` /
`compute_cash_pct` (`domain/portfolio_state.py`). 산출 `_derived-{date}.json` 이 sizing 의
drawdown brake 를 먹임. `_summary` 없음 → graceful `skip_reason` (G8).
`load_derived` 는 `_boundary.load_derived_state` wrapper (sizing↔derive 순환 차단).

## 5a thesis_sync (projection — detector 아님)

Stage 4 accepted **new_entry** candidate 를 `thesis.json` position record 로 결정론 projection.
pure `domain/thesis_projection.py` (`project_edge_source` / `project_spec` / `project_falsifier` /
`collect_citations`); assembly + clock 는 `application/thesis_sync.py`. guard:
`verdict=="accepted"` AND `thesis_kind=="new_entry"` 만; **idempotent** (`thesis_path` 존재 시 skip
— clobber 금지, 수정은 user-gated); multi-falsifier 는 primary 만 projection.

## 5b falsifier_proximity

보유 포지션의 falsifier **근접도** 측정. pure `domain/proximity.py` (`classify` /
`months_between` / `DEFAULT_PROXIMITY_BANDS = {"low_max":0.5, "medium_max":0.9}`).
orchestration `application/falsifier_proximity.py:measure_proximity(position, today, bands,
market_snapshot=None)` — `falsifier.category` 별 분기:
- `time_cap`: 경과/horizon → distance ratio
- `metric_trigger`: v1 은 price-only (market_snapshot 없으면 unmeasurable)
- `event_trigger`: 항상 unmeasurable (5c / ingest 로 위임)

`render_drift_md` → `{ticker_dir}/drift-{date}.md`. G6 결정론, G9 alert-only.

## 5c event_falsifier_linker

event-trigger falsifier 의 **발동 여부** 를 Stage 3 catalyst 와 cross-reference.
pure `domain/event_trigger.py` (`EventTriggerStatus` / `build_stage3_index`).
`application/event_falsifier_linker.py`: store 를 `category="event_trigger"` 필터,
`03-catalyst-events.json` 의 `catalysts + d_type_orphans` index, `evaluate_position` 이
presence/absence × seen_today → triggered/not_triggered/unspecified 매트릭스. G6 (추론 금지) /
G7 (Stage 3 citation 운반) / G8 / G9 (alert-only).

## 5d thesis_expiry

time-horizon **expiry tier** 계산. pure `domain/expiry.py` (`classify_tier` /
`DEFAULT_TIERS = {"notice_days":90, "warn_days":30, "expired_days":0, "overdue_days":-30}` /
`DAYS_PER_MONTH = 30.4375`). `application/thesis_expiry.py:compute_expiry` —
`expiry_dt = entry_dt + horizon_months*DAYS_PER_MONTH`; tier notice/warn/expired/overdue/ok/
unmeasurable; `needs_user_decision` = expired|overdue|warn. `render_expiry_md` →
`{ticker_dir}/expiry-{date}.md`.

## drawdown circuit breaker (−15%)

독립 stage 아님. **탐지** 는 `portfolio_state_derive` (`current_drawdown_pct`), **brake 적용** 은
sizing (`application/sizing.main`: `drawdown_brake_active = current_drawdown_pct >= threshold_pct`
→ `size_one` 절반; G17). circuit breaker = derive → sizing 으로 이어지는 drawdown-brake 경로.
