# `telemetry/audit/` — concern별 subdir 레이아웃

경로 shorthand = `$AUDIT_DIR` (`utils.audit_dir()` / 기본 `telemetry/audit/`). 산출물은 생산자/
concern 별 subdir 로 그룹화된다 (flat 혼재 → 소유 명확화).

```
$AUDIT_DIR/
├── shadow-portfolio/               4-tier paper trade audit (audit_integrity BC)
│   ├── state.json                  4-tier NAV state (cross-day 누적)      [STATE]
│   │      writer: domains/audit_integrity/main.py (결정론 엔진)
│   │      init:   domains/audit_integrity/init_shadow_state.py
│   │      reader: audit-outcome skill (분기 비교, read-only)
│   └── trade-log-{tier}.csv        tier별 closed trade (append)          [PERMANENT]
│          writer: domains/audit_integrity/io/trade_log.py
│          tier ∈ {tier_0_passive_index, tier_1_mechanical, tier_2_llm_filtered, tier_3_random}
│
├── scheduler-state/
│   └── scheduler-state-{date}.{phase}.json   launchd/cron drift 스냅샷    [SNAPSHOT]
│          writer: infrastructure/scheduling/drift_audit.py ($SCHEDULER_STATE_DIR)
│
├── violations/{bc}/{date}.jsonl    BC별 룰 위반 로그 (append-only)        [PERMANENT]
│          writer: domains/_shared/audit/log.py (ViolationLog, bc_name 파라미터화)
│          bc ∈ {screener, universe, catalyst, macro, policy, audit_integrity}
│          정상 run 은 위반 파일을 생성하지 않을 수 있음 (behavior-preserving).
│
├── breadth/macro-breadth-{date}.json         SPX 200d breadth 스냅샷      [PERMANENT]
│          writer: domains/macro/breadth_fetch.py (Stage 0a)
│
└── subsidiaries/subsidiaries-audit-{date}.json  지주사 자회사 audit       [PERMANENT]
           writer: domains/universe/sources/holding_company.py (DART best-effort)
```

## 메모

- **shadow-portfolio/state.json** 은 append-update 되는 living accumulator → `state_store.py` 가
  atomic replace (tmp → os.replace) 로 갱신 (G20 `.{N}` 아님). `init_shadow_state --force` 만 예외.
- **violations** 레이아웃은 `violations/{bc}/` → `violations/{bc}/` 로 일반화됨 (단일 SSoT
  `_shared/audit/log.py` 의 `_log_path`, BC 별 thin subclass).
- **scheduler-state** 는 `$SCHEDULER_STATE_DIR` env(install.sh / launchd_generator)로 주입 —
  기본 `telemetry/audit/scheduler-state`.
- audit-outcome/audit-process skill 산출(`outcome-{YYYY-Q}.md` / `process-{YYYY-WW}.md` /
  `disable-trigger.json`)은 read-only 비교 산물 — 결정론 엔진의 state 와 lifecycle 이 다르다.
- "audit" 3중 의미 주의: `audit_integrity` BC (outcome 감사) vs per-BC `<bc>/audit/` (in-stage 검증)
  vs `_shared/audit/` (kernel ViolationLog).
