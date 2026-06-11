# Audit — runtime-policy + KisAccountPort (in-BC ViolationLog 없음)

## 모델 차이

risk_engine 은 **`audit/` 서브패키지가 없다** (universe 와 대조). in-BC `ViolationLog` / invariant JSONL **없음**. 대신 **정적/타입 guard** 로 안전 강제 — 이것이 risk_engine audit 의 본질.

## 적용 G-guard

| G | 내용 | 적용 |
|---|---|---|
| G5 | asymmetry<2 → reject/half-cap | `domain/sizing.size_one` |
| G6 | 정량 계산 Python 단독 | 모든 `domain/` 산식 |
| G7 | 숫자는 `{source}@{ISO}={value}` citation | `format_citation` |
| G8 | helper 미fetch 데이터 채움 금지 | graceful `skip_reason` / warning |
| **G9/G9a/b/c** | 자동매매 차단 — **본 BC 핵심** | 4중 guard (ports/_boundary/positions_sync) |
| G12 | user context 없으면 size 보류 | `application/sizing` |
| G16 | 단일 25% cap + 합산 Kelly ≤ 0.5 | `per_position.max_pct` / `apply_portfolio_kelly_cap` |
| G17 | drawdown −15% → size 절반 | `drawdown_brake.threshold_pct` |
| G18 | cash% < regime `cash_band[0]` 금지 | `application/sizing` cash-band block |
| G20 | overwrite 금지, date 보존 | `write_output_safely` (`.{N}` suffix) |
| G21 | secret 노출 금지 | `secret_safe_log`, 계좌번호 mask |

## G7 / G20 / G21 inline 강제

- **G7**: 모든 산출 숫자는 `_boundary.format_citation` 으로 citation 부착
- **G20**: 같은 날 재실행은 `.{N}.json` / `.{N}.md` suffix
- **G21**: `secret_safe_log` 로 warning redact, KIS 계좌번호 mask
