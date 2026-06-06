# Audit — G7 citation + minimal violation logging

## 무엇이 강제되는가

### Runtime invariant — main.py 가 호출

**G7 — indicator source_citation 형식**: 각 IndicatorResult 의 `source_citation` 이 정규식 `^[A-Za-z0-9_]+@\S+=.+$` 매칭. 위반 시 severity=`warning` (run 진행).

### JSONL 로그

`$AUDIT_DIR/macro-violations/{YYYY-MM-DD}.jsonl` — append-only. universe / screener 와 동일 패턴.

## ViolationLog 구조

universe 와 동일 (`audit/log.py`). `has_blocking` flag 로 exit code 결정.

## screener / universe 와의 차이

macro 는 N entries 가 아니라 1 RegimeResult + 4 IndicatorResult 만 산출 — 검증 범위가 작음. 향후 invariant 추가 가능:
- breadth.yaml 의 fail_ratio ≥ 0.2 시 G8 graceful skip 가시화
- VIX percentile 계산 시 history N=0 보호
- regime_shift 의 backward scan 에러 누적

## Severity 정책

| severity | exit code | run 진행 |
|---|---|---|
| `blocking` | 2 | 중단 (config_build 실패 등 — 현재 미발생) |
| `warning` | 0 | 진행 |
