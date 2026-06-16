# telemetry/ 개요 — cross-day 감사·관측 증거 스토어

`telemetry/` 는 파이프라인이 날짜를 가로질러 누적하는 **재생성-불가 증거 + 상태**의 루트다
(ADR-0008 분류축: 재생성 가능성 + 수명 + 소유). 루트 path helper = `utils.telemetry_dir()`
(`$TELEMETRY_DIR` override).

## 전체 트리 (정리 후 레이아웃)

```
telemetry/
├── positions/                      보유 포지션 스토어 (→ common/positions-store.md)
│   ├── _account/                   계좌 단위 산출물 (account-level)
│   │   ├── summary-{date}.json     KIS 계좌 스냅샷         [SNAPSHOT]  ← risk_engine/positions_sync
│   │   └── derived-{date}.json     summary scan 파생 state [SNAPSHOT]  ← risk_engine/portfolio_state_derive
│   └── {KR_xxxxxx}/                per-ticker (콜론 sanitize)
│       ├── balance-{date}.json     종목 잔고 스냅샷         [SNAPSHOT]  ← positions_sync
│       ├── thesis.json             falsifier spec machine state [STATE] ← risk_engine/thesis_sync
│       ├── thesis.md               사람용 narrative         [STATE]    ← stage4-thesis-auditor skill
│       ├── drift-{date}.md         반증 근접도 리포트        [SNAPSHOT] ← risk_engine/falsifier_proximity
│       └── expiry-{date}.md        thesis 만료 모니터        [SNAPSHOT] ← risk_engine/thesis_expiry_monitor
│
├── audit/                          감사 trail (→ common/audit-layout.md)
│   ├── shadow-portfolio/
│   │   ├── state.json              4-tier paper trade state [STATE]    ← audit_integrity/main
│   │   └── trade-log-{tier}.csv    tier별 closed trade      [PERMANENT]← audit_integrity/io/trade_log
│   ├── scheduler-state/
│   │   └── scheduler-state-{date}.{phase}.json  launchd/cron drift [SNAPSHOT] ← scheduling/drift_audit
│   ├── violations/{bc}/{date}.jsonl  BC별 위반 로그          [PERMANENT]← _shared/audit/log
│   ├── breadth/macro-breadth-{date}.json  SPX breadth 스냅샷 [PERMANENT]← macro/breadth_fetch
│   └── subsidiaries/subsidiaries-audit-{date}.json  자회사 audit [PERMANENT]← universe/holding_company
│
├── nav-history/{KR_xxxxxx}.jsonl   지주사 NAV 시계열 (append) [PERMANENT]← _shared/nav_history
├── external_signals/{KR_xxxxxx}/{date}-{seq}.md  ingest 증거 [PERMANENT]← ingest-external-signal skill
├── segments/vectors.sqlite         임베딩 벡터 인덱스        [BINARY]   ← universe/segment_index_main
├── policy_drafts/{KR_xxxxxx}/...   commit 전 policy draft    [EPHEMERAL]← policy/main + policy-profiler (gitignore)
└── logs/                           실행 로그                 [EPHEMERAL] (gitignore)
    └── cron/run-{date}.log
```

각 줄의 `[CLASS]` = retention class (→ common/retention-classes.md). `← producer` = 생산 모듈/스킬.

## git 추적 여부

| 영역 | git | 근거 |
|---|---|---|
| positions / audit / nav-history / external_signals / segments | **추적** | 재생성-불가 증거 / 상태 스냅샷 (ADR-0008) |
| logs/ · policy_drafts/ | ignore | EPHEMERAL (실행 로그 / commit 전 draft) |
| `telemetry/**/*.[0-9]*.{json,jsonl,md,csv}` | ignore | G20 `.{N}` 충돌 재실행본 (transient — GC 가 정규화) |
| `.gitkeep` (positions/audit/nav-history) | 추적 | 빈 디렉토리 유지 |

## 디렉토리 vs 코드 불변식

- 코드(`domains/`)와 데이터(`telemetry/`)는 분리. positions 는 데이터이므로 telemetry 에 있고,
  이를 다루는 코드는 `domains/risk_engine/` 에 있다 (스토어를 패키지 내부로 옮기는 것은 안티패턴).
- 경로는 `infrastructure/_common/utils.py` path helper 가 SSoT 로 계산 (env override seam).
- 산출물 종류의 SSoT 는 `infrastructure/_common/telemetry_registry.py` `REGISTRY`.
