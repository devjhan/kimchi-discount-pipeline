# screener — DDD Modular Monolith Overview

투자 파이프라인 Stage 2 의 quality filter + 향후 백테스트 인프라.
`domains/screener/` 패키지가 self-contained bounded context.

## 4 Anchor (변경 시 도메인 안정성 영향)

1. **RuleFactory.build_strategy 단일 진입점** — 모든 Rule 트리 생성은 본 클래스를 통과. 직접 `AndRule(...)` 생성 시 HardGuardWrapper 자동 wrap 이 누락되어 G13 우회 통로가 열린다. test 코드도 예외 없이 factory 사용.

2. **resolver.resolve_metric 화이트리스트** — `rules/resolver.py` 에 등록된 metric_path 만 허용. `eval()` / `getattr(snapshot, dynamic)` 일체 금지. 신규 metric 은 본 모듈에 등록 함수 추가하는 PR — 의도된 마찰 (`02-resolver.md` 참조).

3. **clock.can_see IO 한정** — `Rule.evaluate(snapshot)` 시그너처에 clock 없음. 시점 가시화는 `LiveFinancialCache` / `PointInTimeFinancialCache` 가 단독 책임. 백테스트 결정론 single point of control (`04-cache-contract.md` 참조).

4. **`_boundary.py` 단일 외부 게이트** — 다른 screener 모듈이 `infrastructure.*` (utils / dart.client) 또는 `from_alias`, `os.environ` 직접 호출 시 컨벤션 위반. 외부 의존 추가는 boundary 갱신 + 본 디렉토리 + README cross-ref 동시 PR. 검증: `grep -rn "from infrastructure" domains/screener/` 결과는 `_boundary.py` 1 파일만 (`05-boundaries.md` 참조).

## 패키지 핵심 객체

- `time/clock.py` `AsOfClock` — 시점 t 의 1급 시민 (tz-aware datetime, KST 강제)
- `domain/ticker.py` `TickerSnapshot` / `FilingMetric` — frozen dataclass, derived metric API
- `domain/verdict.py` `RuleResult` / `ScreenVerdict` — Rule 평가 결과
- `rules/` — Rule ABC + leaf (Threshold/Scoring/SignalPresence) + composite (And/Or/Not/WeightedSum) + HardGuardWrapper + factory + resolver + methods
- `io/` — DART adapter / LiveFinancialCache / PointInTime stub / capital_signals / universe_loader / trail_writer
- `audit/` — citation 검증 / violation / invariants / JSONL log
- `application/screen.py` — run_screen orchestrator
- `main.py` — CLI 진입 (`python -m domains.screener.main [--dry-run]`)
- `config/` — profiles / strategies / hard_guards / methods_manifest (self-contained, 외부 thresholds.yaml 의존 없음)

## 산출 / 외부 연결점

산출:
- `$TRAIL_TODAY/02-quality-filter.json` — Stage 3/4/6 + quality-lens skill + audit-shadow 의 5 consumer 가 read. schema `investment-stage2-quality-filter-v1` 보존.
- `$TRAIL_TODAY/02-fin-fetch.json` (선택) — audit 추적 envelope.

상세 boundary 표는 `05-boundaries.md` 와 패키지 `README.md`.
