# Audit — G6 / G7 / G14 invariants + JSONL log

## Runtime invariants (main.py 가 build_universe 후 호출)

1. **G7 — 모든 attribute citation 형식** (`validate_g7_citations`)
   - `EnrichedEntry.source_citation` + `enrichment_citations` 가 정규식 `^[A-Za-z0-9_]+@\S+=.+$` 매칭
   - 위반 시 severity=`warning` (run 진행 — exit 0)

2. **source_category consistency** (`validate_enricher_applies_to`)
   - 각 Enricher 의 `applies_to` 가 runtime entries 의 source_category 와 1개 이상 교집합
   - disjoint 시 orphan enricher — severity=`warning`, `rule_name="enricher_orphan"`

## Build-time invariants (main.py 가 config load 후 호출)

3. **config_build failures** — `build_sources` / `build_enrichers` ValueError
   - severity=`blocking`, `rule_name="config_build"`, exit 2

## Code-review invariants (runtime 검증 부재)

4. **G6 — 산식은 enricher / source 내부에서만** — main.py / build_universe / LLM 재구현 금지
5. **G14 — manual map 외 자동 추가 금지** — subsidiaries.yaml / manual_additions.yaml 외 ticker 자동 등장 X

## ViolationLog 구조

```python
class ViolationLog:
    def __init__(self, clock: AsOfClock): ...
    @property
    def has_blocking(self) -> bool: ...
    def record(self, violation: GuardViolation) -> Path: ...
```

`GuardViolation`: `detected_at` / `severity` / `rule_name` / `ticker` / `message` / `context`

## JSONL 로그 위치

`$AUDIT_DIR/universe-violations/{YYYY-MM-DD}.jsonl` — append-only

## Severity 정책

| severity | exit code | run 진행 |
|---|---|---|
| `blocking` | 2 | 중단 |
| `warning` | 0 | 진행 |
