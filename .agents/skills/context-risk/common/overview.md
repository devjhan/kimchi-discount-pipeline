# risk_engine — Stage 5 Sizing + Monitoring + Account BC (Absorbed)

투자 파이프라인의 **사이징 권고 (Stage 5)** + **thesis 모니터링 (Stage 5a~5d)** + **KIS 계좌 read-only sync** bounded context. screener/universe 와 동형 DDD 레이어링 (`domain/` + `application/` + flat CLI shim, F-8).

## 패키지 구조

```
domains/risk_engine/
  _boundary.py          # 외부 의존 단일 게이트 (infrastructure.* / KIS / positions store)
  ports/                # BC-local Protocol — KisAccountPort (G9c type-level read-only)
    kis_account.py
  domain/               # 순수 규칙 (sizing / proximity / expiry / event_trigger / portfolio_state). IO 0
  application/          # orchestration + IO (sizing / thesis_sync / falsifier_proximity / ...)
  <flat>.py             # thin CLI shim (python -m 진입점 — daily_pipeline.sh 하드코딩)
```

## 3 concern (개념 그룹 — layer 위의 논리 축)

| concern | 모듈 | Stage |
|---|---|---|
| **sizing** | `application/sizing` + `domain/sizing` | 5 |
| **monitor** | `application/{thesis_sync, falsifier_proximity, event_falsifier_linker, thesis_expiry}` + `domain/{proximity, expiry, event_trigger, thesis_projection}` | 5a~5d |
| **account** | `positions_sync` (flat, KIS read) + `application/portfolio_state` + `domain/portfolio_state` | sync / derive |

> **물리 concern 서브패키지 reorg 기각** (ADR-0007) — 재제안 금지. 3 concern 은 논리 축만.

## 4 Anchor

1. **Kelly/sizing 산식 단일 source (G6)** — `domain/sizing.py:compute_fractional_kelly` + `size_one` + `apply_portfolio_kelly_cap`. pure, IO 0.
2. **positions thesis store 단일 source (F-5b)** — `_boundary.positions_store()` 공유 `PositionsStore`.
3. **`_boundary.py` 단일 infra-import 게이트** — `infrastructure.*` 직접 import 금지.
4. **type-level read-only KIS gate (G9c)** — `KisAccountPort` 는 read 6 메서드만 노출.

## CLI 진입점 (daily_pipeline.sh 하드코딩 — flat 모듈명 보존 필수)

```
python -m domains.risk_engine.{positions_sync, portfolio_state_derive, sizing,
                               thesis_sync, falsifier_proximity,
                               event_falsifier_linker, thesis_expiry_monitor}
```

공통 flag: `--date` / `--trail-dir` / `--dry-run`; 일부 `--config` / `--env` / `--lookback-days`.
exit 0 = success. exit 2 = `KisAutoTradeBlocked` fail-loud (G9c, 절대 graceful 아님).

## 외부 연결점

| 방향 | 인터페이스 | 게이트 |
|---|---|---|
| 입력 (KIS 계좌 read) | 6 endpoint (토큰 + 잔고/매수가능/자산/실현손익/매도가능) | `KisAccountPort` ← `_boundary.kis_account_adapter()` |
| 입력 (env) | `KIS_APP_KEY` / `KIS_APP_SECRET` / `KIS_ACCOUNT_NUMBER` | `_boundary.load_env_file()` |
| 입력 (정책) | runtime-policy `kis.read_only_account.enabled` whitelist | `_boundary.kis_read_only_enabled()` |
| 입력 (thresholds) | `governance/thresholds.yaml` (sizing 가드) | `_boundary.load_yaml_config` |
| 입출력 (positions) | `telemetry/positions/*` thesis/balance/derived | `_boundary.positions_store()` (PositionsStore, F-5b) |
| 출력 (산출물) | `$TRAIL_TODAY/05-*.json` + `$POSITIONS_DIR/*` | `_boundary.write_output_safely` (G20) |

## G9 (자동매매 차단) — 4중 구조적 guard

1. `governance/runtime-policy.yaml` — `agent.block_auto_trade: true` (G9a) + KIS whitelist (G9b)
2. `infrastructure/kis/client` — 주문 TR_ID 호출 시 `KisAutoTradeBlocked` raise
3. `governance/runtime-policy.yaml` Bash deny pattern
4. `ports/kis_account.KisAccountPort` — read 6 메서드만, 매매가 type 으로 표현 불가 (G9c)

## Ports & Adapters

**KisAccountPort** (`ports/kis_account.py`) = KIS 계좌 read 6 메서드 Protocol. order/submit/cancel 부재 → 타입상 매매 호출 불가능. `positions_sync.main()` 이 `kis_account_adapter()` 구성 → `sync_account(..., account=...)` 주입 (composition root).

## 산출물 schema

| stage | 출력 | schema |
|---|---|---|
| 5 sizing | `operations/{date}/05-sizing-recommendation.json` | `investment-stage5-sizing-v1` |
| positions_sync | `telemetry/positions/_account/summary-{date}.json` | `investment-positions-sync-v1` |
| portfolio_state_derive | `telemetry/positions/_account/derived-{date}.json` | `investment-portfolio-derived-v1` |
| 5a thesis_sync | `operations/{date}/05a-thesis-sync.json` | `investment-stage5a-thesis-sync-v1` |
| 5b falsifier_proximity | `operations/{date}/05b-falsifier-proximity.json` | `investment-stage5b-falsifier-proximity-v1` |
| 5c event_falsifier_linker | `operations/{date}/event-trigger-status-{date}.json` | `investment-stage5c-event-falsifier-linker-v1` |
| 5d thesis_expiry | `operations/{date}/05d-thesis-expiry.json` | `investment-stage5d-thesis-expiry-v1` |

- `{ticker_dir}` = `ticker.replace(":","_").replace("/","_")`
- 모든 JSON 은 `write_output_safely` (G20, `.{N}` suffix) + `base_report_envelope`
- handoff: `emit_summary_line(STAGE_NAME, ...)`
- cross-day state: `telemetry/positions/` ($POSITIONS_DIR) — risk_engine 은 **stateful BC**
