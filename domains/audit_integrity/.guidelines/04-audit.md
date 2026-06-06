# Audit — violation shim (parity-only) + G-guard

## ViolationLog (`audit/log.py`)

`audit/log.py` 가 `class ViolationLog(_SharedViolationLog)` 정의 (`bc_name="audit_integrity"`).
JSONL: `$AUDIT_DIR/audit_integrity-violations/{date}.jsonl` (append-only,
`_boundary.resolve_path("operations_audit")`). single-violation type = `GuardViolation`
(`audit/violation.py` = `_shared` re-export). citation helper re-export: `CITATION_RE` /
`is_valid_citation` / `filter_valid_citations`.

### parity-only 주의

universe (`audit/invariants.py` 의 named check `validate_g7_citations` /
`validate_enricher_applies_to` 보유) 와 달리, audit_integrity 는 **`invariants.py` 없음**,
`main.py` 가 `ViolationLog` 를 instantiate 하지 않음. shim 은 parity 용으로 존재하되 엔진은
이슈를 `UpdateResult.warnings` 로 surface (logged invariant violation 아님). 본 BC 내
named `rule_name` 문자열: **없음** (shared kernel 기계만). → 이는 향후 채울 수 있는 gap
(아래).

## 적용 G-guard

| G | 내용 | audit_integrity 적용 |
|---|---|---|
| **G9** | 자동매매 차단 — **본 BC 핵심** | broker/order 코드 0; `_boundary` 가격 read 만; account/order endpoint 미사용 (G9c 도달 불요). `AGENTS.md`: "실제 broker 호출 0 — paper trade only" |
| G6 | LLM 계산 금지 | NAV/return/drift/통계 전부 결정론 (`application`+`domain`+`stat_tests`). F-6 으로 LLM skill 에서 회수 |
| G20 | overwrite 금지, append-only | `init_shadow_state` overwrite 거부 (exit 2 / `--force`→`.{N}.json`); state store atomic replace + history 보존. `hard-guards.md` 가 "shadow portfolio state" 명시 |
| G7 | 숫자는 `{source}@{ISO}={value}` citation | 엔진이 `_Ctx.citations` / `_boundary.format_citation` 수집; skill 은 `STAT@{date}={...}` |
| G8 | 가격 미fetch 시 날조 금지 | 가격 미가용 → 진입 보류 + warning ("가격 미가용 — 진입 보류 (G8)"), 절대 fabricate 안 함 |
| G19 | N<30/N<100 통계 forbidden-language | outcome skill 적용 (엔진 아님). `thresholds.yaml.enforcement.forbidden_language.statistical` |

## 향후 (gap)

- (선택) `audit/invariants.py` 추가 + `main.py` 가 `ViolationLog` instantiate — universe 패턴으로
  엔진 이슈를 JSONL 화 (현재는 `UpdateResult.warnings` 만)
- self-disable trigger 발동 시 audit JSONL 영구 기록 (현재 outcome skill 이 `disable-trigger.json`)
