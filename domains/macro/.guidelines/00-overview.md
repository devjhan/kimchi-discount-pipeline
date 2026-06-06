# macro — DDD Modular Monolith Overview

투자 파이프라인 Stage 0 의 결정적 regime classifier. `domains/macro/` 가
self-contained bounded context. universe / screener 와 isomorphic cross-cutting
구조 (boundary + audit + config + guidelines + `signals/` 플러그인). 각 indicator 는
`Signal` (fetch + vote) 플러그인이며 (`@register_signal` + `config/regimes.yaml`
`signals:`), `classify_regime` 은 registry 로 vote 를 조회해 max-severity 만
aggregate (F-9 — screener Rule 패턴의 vote-in-signal 롤아웃).

## 4 Anchor

1. **`_boundary.py` 단일 외부 게이트** — FRED / Yahoo / breadth.yaml load 모두 본 모듈 위임. `infrastructure.*` 직접 import 금지.

2. **`config/regimes.yaml` single source** — 4 indicator 임계값 + cash_band + regime_shift_alert. thresholds.yaml 에 macro 키 부재 (Run 7 이전 완료).

3. **AsOfClock 공유 single source** — `domains._shared.time.clock` 사용. 백테스트 lookahead 차단 시 1줄 override.

4. **envelope schema `investment-stage0-macro-regime-v1` 호환** — legacy `risk_engine.macro_regime` 와 동일 envelope shape. downstream (sizing / brief_gate / audit_process) 보호.

## 패키지 핵심

- `domain/regime.py` `IndicatorResult` / `RegimeResult` — frozen value objects
- `signals/` `Signal` ABC (fetch + vote) + registry/factory + 4 signal (yield_curve / credit_spread / vix / breadth)
- `application/regime_classify.py` `classify_regime` (registry vote 조회 + max-severity aggregation) + `detect_regime_shift`
- `audit/` `ViolationLog` + `GuardViolation` + `is_valid_citation` (universe pattern mirror)
- `breadth_fetch.py` Stage 0a SPX breadth auto-fetch

## 산출 / 외부 연결점

- 산출: `$TRAIL_TODAY/00-macro-regime.json`, `$EXTERNAL_SIGNALS_MACRO_BREADTH_PATH`
- audit log: `$AUDIT_DIR/macro-violations/{date}.jsonl`
- 외부 도메인 호출: 없음 — Stage 0 은 입력 단계, 다음 stage (sizing / brief_gate) 가 산출물 read
- 외부 의존: FRED (yield curve / credit spread / VIX history) / Yahoo (Stage 0a SPX breadth)
