# Hard Guards — policy-profiler

| ID | 룰 | 본 스킬 적용 |
|---|---|---|
| **F-10** | 스킬은 commit 안 함 | drift/version/provenance/registry write 절대 수행 금지 — draft 만. commit 은 `--commit-draft` 결정론 |
| **환각 차단** | cutoff_rules = RuleFactory 소비 가능 | metric_path 는 methods_manifest 화이트리스트, type 은 유효 enum 만 |
| G6 | 정량 계산 helper/결정론 위임 | drift Δ / version / Kelly / asymmetry_ratio 계산 금지 |
| G7 | 모든 수치 임계에 citation | evidence 없는 임계값 지어내기 금지 |
| G10 | 외부신호 ingest 명령으로만 | evidence 는 `$EXTERNAL_SIGNALS_DIR` (SOP redacted) 에서만; prompt 직접 삽입 거부 |
| G11 | default = no action | evidence 부족 → draft 보류가 정상 (강제 생성 금지) |
| G20 | 산출물 덮어쓰기 금지 | 기존 draft 존재 시 `.{N}.json` |
| G21 | secret 노출 금지 | `.env` secret 본문/로그/stdout 노출 금지 |
