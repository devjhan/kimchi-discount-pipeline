# Audit — G7 citation + minimal violation logging

## Runtime invariant

**G7 — indicator source_citation 형식**: 각 IndicatorResult 의 `source_citation` 이 정규식 `^[A-Za-z0-9_]+@\S+=.+$` 매칭. 위반 시 severity=`warning` (run 진행).

## G6 보장

- 모든 정량 계산 (spread / percentile / OAS threshold) 은 `signals/` 내부에서만 — LLM 재계산 금지
- `classify_regime` 은 aggregation 만 담당 (G6)

## JSONL 로그

`$AUDIT_DIR/violations/macro/{YYYY-MM-DD}.jsonl` — append-only. universe / screener 와 동일 패턴.

## ViolationLog 구조

universe 와 동일 (`audit/log.py`). `has_blocking` flag 로 exit code 결정.

## Severity 정책

| severity | exit code | run 진행 |
|---|---|---|
| `blocking` | 2 | 중단 (config_build 실패 등 — 현재 미발생) |
| `warning` | 0 | 진행 |

## screener / universe 와의 차이

macro 는 1 RegimeResult + 4 IndicatorResult 만 산출 — 검증 범위가 작음.
