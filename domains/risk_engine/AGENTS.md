# domains/risk_engine — Stage 5 Sizing + Monitoring + Account BC

투자 파이프라인의 **사이징 권고 (Stage 5)** + **thesis 모니터링 (Stage 5a~5d)** +
**KIS 계좌 read-only sync** bounded context. screener/universe 와 동형 DDD 레이어링
(`domain/` + `application/` + flat CLI shim, F-8). 단 risk_engine 은 (1) KIS 계좌를
*read* 하고 (2) positions thesis 스토어를 소유한다.

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

### 3 concern (개념 그룹 — domain/application 레이어 위의 논리 축)

| concern | 모듈 | Stage |
|---|---|---|
| **sizing** | `application/sizing` + `domain/sizing` | 5 |
| **monitor** | `application/{thesis_sync, falsifier_proximity, event_falsifier_linker, thesis_expiry}` + `domain/{proximity, expiry, event_trigger, thesis_projection}` | 5a~5d |
| **account** | `positions_sync` (flat, KIS read) + `application/portfolio_state` + `domain/portfolio_state` | sync / derive |

> **구조 결정 (2026-06-05, F-17).** concern 을 *물리 서브패키지*(`sizing/ monitor/ account/`)로
> 분리하지 **않는다** — 이미 `domain/`+`application/` 레이어 + flat CLI shim 이 BC 골격을
> 충족하고, concern 축을 더하면 2D 디렉토리(concern×layer) 복잡도 + `positions_sync` byte-diff
> + `daily_pipeline.sh` 하드코딩 경로 churn 대비 이득이 cosmetic. `audit/` 서브패키지도
> **미추가** — risk_engine 은 ViolationLog/GuardViolation 기록 need 가 없다 (`cash_band_violation`
> 은 sizing payload flag 일 뿐). `config/` 지역화도 **보류** — sizing 가드(Kelly fraction/cap)는
> `governance/thresholds.yaml` 의 *doctrine* 이라 잔류가 정합적("governance yaml → config/ 이전
> = 기각" 결정기록 존중). (YAGNI / 맹목 지역화 금지 — 재제안 방지 기록.)

## CLI 진입점 (daily_pipeline.sh 하드코딩 — flat 모듈명 보존 필수)

```
python -m domains.risk_engine.{positions_sync, portfolio_state_derive, sizing,
                               thesis_sync, falsifier_proximity,
                               event_falsifier_linker, thesis_expiry_monitor}
```

## 외부 연결점

| 방향 | 인터페이스 | 게이트 |
|---|---|---|
| 입력 (KIS 계좌 read) | 6 endpoint (토큰 + 잔고/매수가능/자산/실현손익/매도가능) | `KisAccountPort` ← `_boundary.kis_account_adapter()` |
| 입력 (env) | `KIS_APP_KEY` / `KIS_APP_SECRET` / `KIS_ACCOUNT_NUMBER` | `_boundary.load_env_file()` |
| 입력 (정책) | runtime-policy `kis.read_only_account.enabled` whitelist | `_boundary.kis_read_only_enabled()` |
| 입력 (thresholds) | `governance/thresholds.yaml` (sizing 가드) | `_boundary.load_yaml_config` |
| 입출력 (positions) | `telemetry/positions/*` thesis/balance/derived | `_boundary.positions_store()` (PositionsStore, F-5b) |
| 출력 (산출물) | `$TRAIL_TODAY/05-*.json` + `$POSITIONS_DIR/*` | `_boundary.write_output_safely` (G20) |

## Ports & Adapters / G9 단일 게이트

**KisAccountPort (`ports/kis_account.py`)** = KIS 계좌 read 6 메서드 Protocol. surface 에
order/submit/cancel 이 **부재** → 본 port 로는 매매 호출이 *타입상 불가능* = G9 의 **4번째
구조 가드 (type-level read-only)**. 기존 3중 방어 무변경: ① `_boundary` 가 order endpoint
미노출 ② `infrastructure/kis/client` 의 `KisAutoTradeBlocked` ③ `.claude/settings.json`
Bash deny + runtime-policy whitelist. `positions_sync.main()` 이 `kis_account_adapter()`
구성 → `sync_account(..., account=...)` 주입 (composition root).

패턴 본문: `domains/screener/.guidelines/05-boundaries.md` "Ports & Adapters".

## 검증

```bash
# DDD boundary — infra import 은 _boundary.py 만
grep -rn "from infrastructure\|import infrastructure" domains/risk_engine/ | grep -v _boundary.py   # → 0
# KisAccountPort surface = read 6 (order/submit/cancel 부재 — tests/unit/test_positions_sync.py 회귀)
```
