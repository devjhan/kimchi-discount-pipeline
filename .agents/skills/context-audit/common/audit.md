# Audit — violation shim (parity-only) + G-guard

## ViolationLog (`audit/log.py`)

`ViolationLog` — `_SharedViolationLog` subclass (`bc_name="audit_integrity"`). JSONL: `$AUDIT_DIR/violations/audit_integrity/{date}.jsonl`.

### parity-only 주의

`invariants.py` 없음, `main.py` 가 `ViolationLog` instantiate 하지 않음. 엔진 이슈는 `UpdateResult.warnings` 로 surface. 본 BC 내 named `rule_name` 문자열: **없음**.

## 적용 G-guard

| G | 내용 | audit_integrity 적용 |
|---|---|---|
| **G9** | 자동매매 차단 — **본 BC 핵심** | broker/order 코드 0; `_boundary` 가격 read 만; account/order endpoint 미사용 (G9c 도달 불요) |
| G6 | LLM 계산 금지 | NAV/return/drift/통계 전부 결정론. F-6 으로 LLM skill 에서 회수 |
| G20 | overwrite 금지, append-only | `init_shadow_state` overwrite 거부 (exit 2 / `--force`→`.{N}.json`); state store atomic replace + history 보존 |
| G7 | 숫자는 `{source}@{ISO}={value}` citation | 엔진이 `_Ctx.citations` / `_boundary.format_citation` 수집; skill 은 `STAT@{date}={...}` |
| G8 | 가격 미fetch 시 날조 금지 | 가격 미가용 → 진입 보류 + warning, 절대 fabricate 안 함 |
| G19 | N<30/N<100 통계 forbidden-language | outcome skill 적용 (엔진 아님) |

## 향후 (gap)

- (선택) `audit/invariants.py` 추가 + `main.py` 가 `ViolationLog` instantiate
- self-disable trigger 발동 시 audit JSONL 영구 기록 (현재 outcome skill 이 `disable-trigger.json`)
