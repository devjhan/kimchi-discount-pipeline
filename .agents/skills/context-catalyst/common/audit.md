# Audit — G7 invariant + JSONL log

## Build-time invariant

- **config_build failure** — `build_detectors` 가 `ValueError` (미등록 type / 필수 키 누락) raise 시:
  severity=`blocking`, `rule_name="config_build"`. main.py exit 2 + ViolationLog 기록.

## Code-defined invariant (main.py 미연결 — 의도된 behavior-preserving)

- **G7 citation 형식** (`audit/invariants.py:validate_g7_citations`) — 각 event 의 `source_citation` + `metadata["additional_citations"]` 를 G7 정규식 검사. **현재 main.py 가 호출 안 함** — healthy run 은 `catalyst-violations` 파일을 생성하지 않음 (구 catalyst_scan 과 behavior-preserving).

> universe 와의 차이: universe 는 실제 호출, catalyst 는 함수 보유하되 미연결.

## ViolationLog 구조

`ViolationLog` 는 `domains/_shared/audit/log.py` 의 thin subclass (`bc_name="catalyst"` 고정).

```python
class ViolationLog:
    def __init__(self, clock: AsOfClock): ...
    @property
    def has_blocking(self) -> bool: ...
    def record(self, violation: GuardViolation) -> Path: ...
```

`GuardViolation`: `detected_at` / `severity` / `rule_name` / `ticker` / `message` / `context`

## JSONL 로그 위치

`$AUDIT_DIR/catalyst-violations/{YYYY-MM-DD}.jsonl` — append-only. 현재는 config_build 실패 시에만 생성.

## 적용 G-guard

| G | 내용 | catalyst 적용 |
|---|---|---|
| G6 | 정량 계산은 Python helper 단독 | drop% / lookback 은 `io/earnings_panic_fetch` 등 helper |
| G7 | 모든 숫자는 `{source}@{ISO}={value}` citation | `event.source_citation` via `format_citation` |
| G8 | source 미가용 시 graceful, hallucination 금지 | detector 가 warning + skip |
| G14 | universe 외 ticker 자동 등장 금지 | 모든 detector 가 `ticker in ctx.universe` gate |
| G15 | d_type 단독 trigger 불가 | `augment_d_type_into_primary` orphan 제외 |
| G20 | 산출 overwrite 금지 | `write_output_safely` (collision → `.{N}.json`) |
| G21 | secret 노출 금지 | warning 전체 `secret_safe_log` |
