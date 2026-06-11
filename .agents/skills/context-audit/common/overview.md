# audit_integrity — 4-tier Shadow Portfolio Audit BC (paper-trade only, Absorbed)

LLM filter 의 부가가치를 검증하는 **4-tier shadow portfolio** (Index / Mechanical / LLM-Filtered / Random) 의 결정론 엔진. 일별로 4 tier 의 NAV 를 paper-trade 갱신, 분기 누적 수익률 비교, tier_2(LLM) < tier_1(Mechanical) 4분기 연속 시 self-disable trigger 발동. **실제 broker 호출 없음 (G9).**

## 패키지 구조

```
domains/audit_integrity/
  _boundary.py          # 외부 의존 단일 게이트 (KIS/Yahoo price read / thresholds / 경로)
  main.py               # 일별 결정론 갱신 엔진 (F-6 — 구 LLM 스킬 회수)
  init_shadow_state.py  # 4-tier state --init 템플릿 (1회, --force)
  stat_tests.py         # 순수 통계 lib (Welch t-test / bootstrap / self-disable)
  domain/state.py       # ShadowState 값 객체 + serde
  application/          # tier 갱신 orchestration (run_daily_update.py)
  audit/                # citation + violation log
  io/                   # price fetch 어댑터
```

> **명명 주의 (catch #7):** "audit" 3중 의미 — (1) 본 BC `audit_integrity` (outcome 감사), (2) per-BC `<bc>/audit/` (in-stage 검증), (3) `_shared/audit/` (kernel 원시).

## 4 Anchor

1. **paper-trade only / 실제 체결 0 (G9)** — `_boundary` 는 가격 read 함수만 (`kis_fetch_daily_ohlcv` / `yahoo_fetch_daily_ohlcv`)
2. **stat-test 단일 source (G6 / ADR-0003)** — 모든 통계는 `stat_tests.py` 에만
3. **`_boundary.py` 단일 외부 게이트** — 유일 예외: `init_shadow_state.py` (allowlist, bootstrap 스크립트)
4. **G20 append-only state** — `init_shadow_state` 는 기존 state overwrite 거부 (exit 2, `--force` 시 `.{N}.json`)

## 4 tier 구성

| key | name (default) | holdings 결정 |
|---|---|---|
| `tier_0_passive_index` | `"SPY+KOSPI200 50/50"` | US:SPY, KR:069500 equal-weight 50/50 |
| `tier_1_mechanical` | `"score-only top-K, no LLM"` | `03-catalyst-events.json` top-K primary |
| `tier_2_llm_filtered` | `"system actual recommendations"` | `05-sizing-recommendation.json` `size_recommended` ticker |
| `tier_3_random` | `"random K from same A∩C universe"` | `01-universe ∩ 02-quality(pass)` date-hash seed 로 K 개 |

## 외부 연결점

| 방향 | 인터페이스 | 게이트 |
|---|---|---|
| 입력 (price) | 일별 OHLCV (KIS) | `_boundary.kis_fetch_daily_ohlcv` |
| 입력 (Yahoo) | KIS fallback | `_boundary.yahoo_fetch_daily_ohlcv` (게이트 `resolve_allow_yahoo_fallback`) |
| 입력 (config) | `thresholds.yaml.statistics` | `_boundary.load_thresholds` |
| 입력 (universe/verdicts) | `$TRAIL_TODAY/01-universe.json` / `02-quality-filter.json` | `_boundary.resolve_trail_dir` |
| 입출력 (state) | `$AUDIT_DIR/shadow-portfolio-state.json` | `_boundary.write_output_safely` (G20) |

## CLI

- `python -m domains.audit_integrity.main`: `--date` / `--allow-yahoo-fallback`. exit 0 = success; exit 2 = state 부재.
- `init_shadow_state.py`: `--date` / `--config` / `--trail-dir` / `--force`. exit 2 = state 존재 & `--force` 없음.

## 산출물

- `$AUDIT_DIR/shadow-portfolio-state.json` — accumulator
- `$AUDIT_DIR/trade-log-{tier}.csv` — tier 별 closed trade
- `$AUDIT_DIR/audit_integrity-violations/{date}.jsonl` — violation log
- (read-only outcome skill): `$AUDIT_DIR/outcome-{YYYY-Q}.md` / `$AUDIT_DIR/disable-trigger.json`

## init_shadow_state.py 특수 역할

one-shot composition-root / bootstrap 스크립트. `infrastructure._common.utils` 에서 top-level 직접 import → `BOUNDARY_C_ALLOWLIST` 의 단일 entry. 불변식 C 가 flag 안 함.
