# Audit — G6 / G7 / G14 invariants + JSONL log

## 무엇이 강제되는가 (Run 6 시점)

### Runtime invariants — main.py 가 build_universe 후 호출

1. **G7 — 모든 attribute citation 형식** (`validate_g7_citations`)
   - `EnrichedEntry.source_citation` + `enrichment_citations` 가 정규식 `^[A-Za-z0-9_]+@\S+=.+$` 매칭
   - 위반 시 severity=`warning` (run 자체는 진행 — exit 0)
   - JSONL log 에 `rule_name="g7_citation_format"`, `ticker=<bad_entry>`, `context.source_category=<cat>`, `message=malformed citations: [...]`

2. **source_category consistency** (`validate_enricher_applies_to`) — *runtime* 검증
   - 각 Enricher 의 `applies_to` 집합이 **build_universe 산출 entries 의 source_category 집합** 과 1개 이상 교집합 가져야 함
   - disjoint 시 orphan enricher — severity=`warning`, `rule_name="enricher_orphan"`
   - **runtime vs static**: static config (sources.yaml 의 declared source_category) 가 아닌 *runtime entries* 기준. declared 카테고리에 매칭돼도 실제 entry 가 emit 안 되면 (DART skip / subsidiaries.yaml 빈 등) dead code 로 잡힘. 본 fix 는 2026-05-17 외부 감사 결과 — HoldingCompanySource 가 entries=() 였던 시점 NavDiscountEnricher 가 unreachable 였음.

### Build-time invariants — main.py 가 config load 후 호출

3. **config_build failures** — `build_sources` / `build_enrichers` 가 `ValueError` raise 시
   - severity=`blocking`, `rule_name="config_build"`
   - main.py 가 exit 2 + ViolationLog 에 1건 기록 후 종료

### Code-review invariants — runtime 검증 부재, .guidelines 차원

4. **G6 — 산식은 enricher / source 내부에서만**
   - NAV 합산 / z-score / spread% 등 수치 계산 함수는 한 모듈 내부에 단독 정의
   - main.py / build_universe / 외부 LLM skill 어디에서도 재구현 금지
   - 강제 메커니즘: 코드 리뷰 + 본 문서 인용

5. **G14 — manual map 외 자동 추가 금지**
   - subsidiaries.yaml / manual_additions.yaml 외 ticker 가 universe 에 자동 등장 X
   - 현재 모든 sources 는 명시적 spec / 외부 공시 (DART) 매칭 기반 — auto-inference 없음
   - 향후 ML / heuristic 기반 source 추가 시 본 invariant 신규 runtime check 추가 필요

## ViolationLog 구조 (`audit/log.py`)

```python
class ViolationLog:
    def __init__(self, clock: AsOfClock): ...

    @property
    def has_blocking(self) -> bool: ...

    def record(self, violation: GuardViolation) -> Path:
        # severity='blocking' 이면 has_blocking=True
        # JSONL append to $AUDIT_DIR/universe-violations/{clock.trading_date}.jsonl
        ...
```

`GuardViolation`:
```python
@dataclass(frozen=True)
class GuardViolation:
    detected_at: datetime
    severity: str         # "blocking" | "warning"
    rule_name: str        # "g7_citation_format" / "enricher_orphan" / "config_build" 등
    ticker: str | None
    message: str
    context: dict[str, Any]
```

## JSONL 로그 위치

`$AUDIT_DIR/universe-violations/{YYYY-MM-DD}.jsonl` — append-only, 같은 날 다중 run 도 모두 누적. 다음 stage (audit_process skill) 가 본 로그를 read.

JSONL 한 줄 예:
```json
{"detected_at":"2026-05-17T15:30:00+09:00","severity":"warning","rule_name":"g7_citation_format","ticker":"KR:003550","message":"malformed citations: ['bad-citation']","context":{"source_category":"holding_company"}}
```

## Severity 정책

| severity | exit code | run 진행 | 사용 케이스 |
|---|---|---|---|
| `blocking` | 2 | 중단 | config build 실패 / 미등록 source type / 미등록 enricher type / required field 누락 |
| `warning` | 0 (다른 blocking 없으면) | 진행 | G7 malformed citation / orphan enricher / DART skip (graceful G8 degrade) |

## main.py 통합 패턴

```python
violation_log = ViolationLog(clock)

# build-time: config_build (severity=blocking)
try:
    sources = build_sources(sources_cfg["sources"])
    enrichers = build_enrichers(enrichers_cfg["enrichers"])
except ValueError as exc:
    violation_log.record(GuardViolation(
        detected_at=_boundary.now_kst(),
        severity="blocking", rule_name="config_build",
        ticker=None, message=str(exc),
        context={"sources": ..., "enrichers": ...},
    ))
    return 2

# ... orchestrate ...

# runtime: g7_citation_format / enricher_orphan (severity=warning)
_emit_runtime_invariant_violations(
    result_entries=result.entries,
    sources=sources,
    enrichers=enrichers,
    violation_log=violation_log,
)

return 2 if violation_log.has_blocking else 0
```

## screener 패턴 직역 / 차이

본 모듈은 `domains/screener/audit/log.py` + `violation.py` + `citation.py` 와 isomorphic. 차이:

- 디렉토리 이름: `universe-violations/` (screener: `screener-violations/`)
- `invariants.py` 의 검사 함수 set 이 다름 (screener: hard_guard override / unregistered method; universe: g7 citation / enricher orphan)
- screener 의 invariant 는 build-time 중심 (severity=blocking → exit 2), universe 는 runtime 중심 (severity=warning → exit 0 보장)

## 향후 확장 (Run 6 이후)

- Per-entry metadata schema 검증 (e.g., preferred_share_pair 의 metadata.common/preferred 필수)
- G6 정적 검사 — AST 기반 산식 패턴 매칭 (build-time, 가능하면 PreToolUse hook)
- 분기 outcome audit (audit-outcome skill) 가 본 JSONL 누적 read
