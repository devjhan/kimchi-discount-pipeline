# Telemetry Artifact Registry — kind SSoT

`infrastructure/_common/telemetry_registry.py` 의 `REGISTRY` 가 telemetry 산출물 종류의 단일
진실원천이다. 아래 표는 그 mirror — `tests/architecture/test_telemetry_registry.py` 가 모든
`REGISTRY.kind` 가 본 문서에 등재됐는지 검사한다 (문서-코드 동기화 강제).

| kind | glob (telemetry/ 기준) | retention | producer |
|---|---|---|---|
| `positions_account_summary` | `positions/_account/summary-*.json` | SNAPSHOT | `domains.risk_engine.positions_sync` |
| `positions_account_derived` | `positions/_account/derived-*.json` | SNAPSHOT | `domains.risk_engine.portfolio_state_derive` |
| `positions_ticker_balance` | `positions/*/balance-*.json` | SNAPSHOT | `domains.risk_engine.positions_sync` |
| `positions_ticker_thesis_json` | `positions/*/thesis.json` | STATE | `domains.risk_engine.thesis_sync` |
| `positions_ticker_thesis_md` | `positions/*/thesis.md` | STATE | stage4-thesis-auditor skill |
| `positions_ticker_drift` | `positions/*/drift-*.md` | SNAPSHOT | `domains.risk_engine.falsifier_proximity` |
| `positions_ticker_expiry` | `positions/*/expiry-*.md` | SNAPSHOT | `domains.risk_engine.thesis_expiry_monitor` |
| `nav_history` | `nav-history/*.jsonl` | PERMANENT | `domains._shared.nav_history` |
| `external_signal_intake` | `external_signals/*/*.md` | PERMANENT | ingest-external-signal skill |
| `segments_vector_store` | `segments/vectors.sqlite` | BINARY | `domains.universe.segment_index_main` |
| `audit_violations` | `audit/violations/*/*.jsonl` | PERMANENT | `domains._shared.audit.log` |
| `audit_breadth` | `audit/breadth/macro-breadth-*.json` | PERMANENT | `domains.macro.breadth_fetch` |
| `audit_subsidiaries` | `audit/subsidiaries/subsidiaries-audit-*.json` | PERMANENT | `domains.universe.sources.holding_company` |
| `audit_shadow_state` | `audit/shadow-portfolio/state.json` | STATE | `domains.audit_integrity.main` |
| `audit_shadow_trade_log` | `audit/shadow-portfolio/trade-log-*.csv` | PERMANENT | `domains.audit_integrity.io.trade_log` |
| `audit_scheduler_state` | `audit/scheduler-state/scheduler-state-*.json` | SNAPSHOT | `infrastructure.scheduling.drift_audit` |
| `policy_draft_intake` | `policy_drafts/*/_intake-*.json` | EPHEMERAL | `domains.policy.main` |
| `policy_draft_profile` | `policy_drafts/*/_profile-draft-*.json` | EPHEMERAL | policy-profiler skill + `domains.policy.main --commit-draft` |
| `logs_cron` | `logs/cron/run-*.log` | EPHEMERAL | run_daily_local.sh / daily_pipeline.sh |

`ArtifactKind` 필드: `kind / glob / retention_class / producer_module / producer / scope_segment /
scope_on_stem / id_validator / dated`. `producer_module=None` = 외부 생산자(skill/shell/manual,
존재성 검사 N/A). `id_validator=^KR_\d+$` = ticker scope 검증 (bare 6-digit 위반 → ORPHAN).

## 신 산출물 종류 추가 절차

1. writer(producer) 모듈을 path helper 경유로 작성 (`utils.*_dir()` 또는 `_boundary.resolve_path`).
2. `REGISTRY` 에 `ArtifactKind(...)` 1엔트리 추가 (glob/retention/producer_module/scope/id).
3. 본 표(common/artifact-registry.md)에 행 추가 — arch 테스트가 동기화 검사.
4. `make telemetry-gc` dry-run 으로 ORPHAN 0 확인.
5. retention class 선택 가이드: append-only 증거→PERMANENT, 날짜 미박힌 living state→STATE,
   point-in-time mirror/파생→SNAPSHOT, 바이너리 증거→BINARY, gitignore 로그/draft→EPHEMERAL.
