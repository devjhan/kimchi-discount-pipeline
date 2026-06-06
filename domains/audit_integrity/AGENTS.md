# domains/audit_integrity — 4-tier Shadow Portfolio Audit BC (paper-trade only)

LLM filter 의 부가가치를 검증하는 **4-tier shadow portfolio** (Index / Mechanical /
LLM-Filtered / Random) 의 결정론 엔진. 일별로 4 tier 의 NAV 를 paper-trade 갱신하고,
분기 누적 수익률을 비교해 tier_2(LLM) < tier_1(Mechanical) 4분기 연속 시 self-disable
trigger 를 발동한다 (통계적 정직성 — 5대 철학 #5). **실제 broker 호출 없음 (G9).**

## 패키지 구조

```
domains/audit_integrity/
  _boundary.py          # 외부 의존 단일 게이트 (KIS/Yahoo price read / thresholds / 경로)
  main.py               # 일별 결정론 갱신 엔진 (F-6 — 구 LLM 스킬 회수). python -m ...main
  init_shadow_state.py  # 4-tier state --init 템플릿 (1회, --force). 구 shadow_portfolio.py (F-17)
  stat_tests.py         # 순수 통계 lib (investment-audit-outcome 스킬이 분기 비교에 소비)
  domain/state.py       # ShadowState 값 객체 + serde (on-disk JSON ↔ dataclass)
  application/          # tier 갱신 orchestration
  audit/                # citation + violation log
  io/                   # price fetch 어댑터
```

> **명명 주의 (catch #7).** "audit" 3중 의미: (1) 본 BC `audit_integrity` (outcome 감사),
> (2) per-BC `<bc>/audit/` (in-stage 검증 기록), (3) `_shared/audit/` (kernel 원시).
> 상세: `domains/_shared/__init__.py`.

## 외부 연결점

| 방향 | 인터페이스 | 게이트 |
|---|---|---|
| 입력 (price) | 4-tier NAV 평가용 일별 OHLCV (KIS) | `_boundary.kis_fetch_daily_ohlcv` |
| 입력 (Yahoo) | KIS fallback | `_boundary.yahoo_fetch_daily_ohlcv` (`resolve_allow_yahoo_fallback` 게이트) |
| 입력 (config) | `governance/thresholds.yaml.statistics` (benchmark_tiers / shadow_portfolio / self_disable) | `_boundary.load_thresholds` |
| 입력 (universe/verdicts) | `$TRAIL_TODAY/01-universe.json` · `02-quality-filter.json` (tier pool) | `_boundary.resolve_trail_dir` |
| 입출력 (state) | `$AUDIT_DIR/shadow-portfolio-state.json` (재생성-불가 누적 증거) | `_boundary.write_output_safely` (G20 append-only) |

## 하드 가드

- **G9**: 실제 broker 호출 0 — paper trade only. `init_shadow_state` / `main` 모두 price read 만.
- **G6**: NAV / 수익률 모든 정량은 본 BC 결정론 산식 (LLM 위임 금지 — F-6 회수 교훈,
  [ADR-0003](../../governance/decisions/0003-llm-drafts-python-commits.md)).
- **G20**: shadow-portfolio-state 덮어쓰기 금지 (`init_shadow_state --force` 필수).
- **통계 정직성**: N<10 alpha 주장 금지 등 sample gate (`stat_tests` + outcome 스킬).

## 검증

```bash
grep -rn "from infrastructure\|import infrastructure" domains/audit_integrity/ --include="*.py" | grep -v _boundary.py   # → 0
# G9: KIS order TR_ID / broker write 부재 (price read endpoint 만)
```
