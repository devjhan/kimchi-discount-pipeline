# `telemetry/positions/` — 보유 포지션 스토어 계약 (SSoT)

`schema: positions-store-contract-v1` · 구 `telemetry/positions/README.md` 흡수.

보유 포지션의 **cross-day state** 를 담는 **multi-owner 데이터 스토어**. 경로 shorthand =
`$POSITIONS_DIR` (`utils.positions_dir()` / 기본 `telemetry/positions/`); account-level 산출물은
`utils.positions_account_dir()` (`telemetry/positions/_account/`, `$POSITIONS_ACCOUNT_DIR` override).

## 1. 왜 risk_engine 안이 아니라 telemetry 인가

- **code↔data 불변식**: 코드(`domains/`)와 데이터(`telemetry/`)는 분리. positions 는 데이터이므로
  `telemetry/` 에 있고, 이를 다루는 코드는 `domains/risk_engine/` 에 있다.
- **multi-owner**: positions 는 risk_engine 사유물이 아니다. `thesis`(falsifier spec)는
  stage4-thesis-auditor skill + 사용자가 저작; risk_engine 은 `balance`/`summary`/`derived`/
  `drift`/`expiry` 같은 기계적 파생물만 쓴다. 읽기는 risk_engine + brief/audit skill cross-cutting.
  → risk_engine 패키지 *안으로* 옮기는 것은 안티패턴.

## 2. 스토어 레이아웃

```
$POSITIONS_DIR/
├── _account/                       account-level (account_dir; ticker dir 과 분리)
│   ├── summary-{date}.json         계좌 일별 스냅샷 (총자산/현금/보유수/실현손익)  [SNAPSHOT]
│   │      schema: investment-positions-sync-v1
│   │      writer: domains/risk_engine/positions_sync.py  (KIS read-only sync)
│   └── derived-{date}.json         파생 포트폴리오 state (drawdown% / cash%)        [SNAPSHOT]
│          schema: investment-portfolio-derived-v1
│          writer: domains/risk_engine/portfolio_state_derive.py
│          reader: domains/risk_engine/application/sizing.py (portfolio.yaml null fallback)
│
└── {ticker_dir}/                   종목 디렉토리 (콜론 sanitize: KR:003550 → "KR_003550")
    ├── balance-{date}.json         종목별 보유 스냅샷                               [SNAPSHOT]
    │      writer: positions_sync.py · schema: investment-positions-sync-v1-perticker
    ├── thesis.json                 MACHINE STATE — falsifier spec (§3)             [STATE]
    │      writer: domains/risk_engine/thesis_sync.py (Stage 5a)
    ├── thesis.md                   NARRATIVE — 사람용 thesis 본문 (§3)             [STATE]
    │      author: stage4-thesis-auditor skill / 사용자 (명시 명령 시에만)
    ├── drift-{date}.md             falsifier proximity 리포트                       [SNAPSHOT]
    │      writer: domains/risk_engine/falsifier_proximity.py
    └── expiry-{date}.md            thesis time-horizon 만료 모니터                  [SNAPSHOT]
           writer: domains/risk_engine/thesis_expiry_monitor.py
```

공통 규칙:
- **retention** (→ retention-classes.md): `summary`/`derived`/`balance`/`drift`/`expiry` 는
  SNAPSHOT — (kind, scope)별 **최신 1건**만 보존 (이전 날짜는 GC 가 stale 로 정리). `thesis.json`/
  `thesis.md` 는 STATE — living 단일 파일, GC 미prune. NAV 시계열 증거는 `telemetry/nav-history/`
  (PERMANENT) 가 별도 소유.
- **G20**: 모든 writer 는 `write_output_safely` 경유 — 충돌 시 `.{N}` suffix (GC 가 최신본만 정규화).
- **G7 (citation)**: 모든 잔고/현금/평가 숫자는 source citation 보유 (`KIS@<ts>=<value>` 등).
- JSON 산출물은 `base_report_envelope` 래핑(`schema`/`generated_at`/`date` + `payload`).
- ticker dir 식별자는 `^KR_\d+$` (bare 6-digit 은 레거시 — GC ORPHAN).

## 3. `thesis.json` (machine state) vs `thesis.md` (narrative)

| | `thesis.json` | `thesis.md` |
|---|---|---|
| 성격 | 기계 판독 state (falsifier spec) | 사람용 narrative |
| 저자 | `thesis_sync.py` (Stage 5a, 04-thesis-candidates 파생) / 사용자 | stage4-thesis-auditor skill / 사용자 (명시 명령 시) |
| 소비자 | risk_engine Python (일별 monitoring) | 사람 + stage4 skill (amendment 판단 입력) |

`thesis.json` 기대 shape (`falsifier_proximity` / `thesis_expiry_monitor` /
`event_falsifier_linker` 가 load, `status != "open"` 이면 skip):

```json
{
  "ticker": "KR:003550", "name": "LG", "entry_date": "2026-01-15",
  "entry_price_krw": 84000, "status": "open",
  "thesis": {
    "entry_catalyst": "...",
    "falsifier": {"category": "time_cap | metric_trigger | event_trigger", "spec": {}},
    "time_horizon_months": 18, "edge_source": ["C", "D"], "asymmetry_score": {}
  }
}
```

5 필드(`entry_catalyst`/`falsifier`/`time_horizon_months`/`edge_source`/`asymmetry_score`)는
stage4 가 `04-thesis-candidates.json` 으로 산출하는 thesis schema 와 동형. `thesis.md` 존재
여부로 thesis_kind(new_entry vs amendment)를 분류. risk_engine Python 은 `thesis.md` 를 읽지 않음.

## 4. `thesis.json` writer — Stage 5a Thesis Sync

`thesis.json` 은 **구조화된** `04-thesis-candidates.json` 에서 결정론 파생된다 (narrative `thesis.md`
의 LLM markdown 파싱이 아니라 — fragility 회피).

- writer: `domains/risk_engine/thesis_sync.py` (Stage 5a). `daily_pipeline.sh` post-stage4 phase 에서
  5b/5c/5d monitor **앞**에 실행.
- 불변식: `verdict=="accepted"` AND `thesis_kind=="new_entry"` 후보만 write. amendment /
  needs_user_decision / 보유 포지션은 절대 auto-write 안 함(user-gated). **멱등** — 기존 `thesis.json`
  존재 시 clobber 금지.

## 5. 접근 패턴 (F-5b)

- positions 스키마/접근은 `domains/_shared/positions_store/` 가 소유 (`profile_registry` 와 동형:
  schema + serde + injected-writer). `infrastructure` import 0 — root·writer 는 caller 가 주입.
- risk_engine 은 `domains/risk_engine/_boundary.py` 단일 게이트로만 외부 접근 (path /
  `resolve_positions_dir` / `resolve_account_dir` / KIS read-only / `positions_store` / `derived` read).
