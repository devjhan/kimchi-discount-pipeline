# Audit — G7 invariant + JSONL log

## 무엇이 강제되는가

### Build-time invariant — main.py 가 config load 후 호출
- **config_build failure** — `build_detectors` 가 `ValueError` (미등록 type / 필수 키 누락) raise 시:
  severity=`blocking`, `rule_name="config_build"`. main.py 가 stderr 출력 + ViolationLog 1건
  기록 후 exit 2.

### Code-defined invariant — main.py 미연결 (의도된 behavior-preserving)
- **G7 citation 형식** (`audit/invariants.py:validate_g7_citations`) —
  `validate_g7_citations(events) -> list[CitationViolation]`. 각 event 의 `source_citation` +
  `metadata["additional_citations"]` 를 G7 정규식 (`domains._shared.audit.citation.is_valid_citation`)
  으로 검사. 빈 `source_citation` 은 무시. `CitationViolation(catalyst_id, ticker, bad_citations)`
  (frozen) 반환.
  - **현재 main.py 가 호출 안 함** — 구 `catalyst_scan` 이 violation log 를 안 썼으므로,
    behavior-preserving 위해 healthy run 은 `catalyst-violations` 파일을 **생성하지 않는다**.
    재배선 (universe 처럼 build 후 호출 → warning 기록) 은 향후 확장 (아래).

> universe 와의 차이: universe 는 `validate_g7_citations` / `validate_enricher_applies_to`
> 를 build 후 실제 호출 (산출물 있으면 warning JSONL). catalyst 는 invariant 함수는
> 보유하되 미연결 — `04-audit.md` 가 이 gap 을 명시적으로 기록.

## ViolationLog 구조 (`audit/log.py`)

`domains/catalyst/audit/log.py:ViolationLog` 는 `domains/_shared/audit/log.py:ViolationLog`
의 thin subclass (`bc_name="catalyst"` 고정, `audit_dir=lambda: _boundary.resolve_path("operations_audit")`).
shared base API:

```python
class ViolationLog:
    def __init__(self, clock: AsOfClock): ...
    @property
    def has_blocking(self) -> bool: ...        # severity=="blocking" 기록 시 True
    def record(self, violation: GuardViolation) -> Path: ...   # JSONL 1줄 append
    # _log_path() → {audit_dir}/catalyst-violations/{trading_date}.jsonl
```

`GuardViolation` (`_shared/audit/violation.py`, re-export):
```python
@dataclass(frozen=True)
class GuardViolation:
    detected_at: datetime
    severity: str        # "blocking" | "warning"
    rule_name: str       # "config_build" 등
    ticker: str | None
    message: str
    context: dict[str, Any] = field(default_factory=dict)
```

## JSONL 로그 위치

`$AUDIT_DIR/catalyst-violations/{YYYY-MM-DD}.jsonl` — append-only. 현재는 config_build
실패 시에만 생성 (healthy run 은 없음).

## 적용 G-guard

| G | 내용 | catalyst 적용 |
|---|---|---|
| G6 | 정량 계산은 Python helper 단독, LLM 재계산 금지 | drop% / lookback 은 `io/earnings_panic_fetch` 등 helper |
| G7 | 모든 숫자는 `{source}@{ISO}={value}` citation | event.source_citation 은 `_boundary.format_citation`; `validate_g7_citations` 검사 함수 보유 |
| G8 | source 미가용 시 graceful, hallucination 금지 | detector 가 warning + skip; `earnings_panic` 은 `price_source="unavailable"` 반환 (가격 날조 X) |
| G14 | universe 외 ticker 자동 등장 금지 | 모든 detector 가 `ticker in ctx.universe` gate |
| G15 | d_type 단독 trigger 불가 | `augment_d_type_into_primary` orphan 제외 (`02-scan.md`) |
| G20 | 산출 overwrite 금지, date-keyed | `write_output_safely` (collision → `.{N}.json`) |
| G21 | secret 노출 금지 | warning 전체 `secret_safe_log`; `dart_has_key`/`kis_has_keys` 는 존재만 확인 |

## 향후 확장

- `validate_g7_citations` 를 main.py build 후 호출 (universe 패턴) — warning JSONL 활성화
- per-event metadata schema 검증 (예: d_type augment 구조)
- 분기 outcome audit (`investment-audit-outcome` skill) 가 본 JSONL 누적 read
