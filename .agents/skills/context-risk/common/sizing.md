# Sizing — Stage 5 fractional Kelly + cap

## 산식 단일 source (`domain/sizing.py`, pure, G6)

```python
def compute_fractional_kelly(asymmetry_ratio: float, fraction: float) -> float:
    # f* = p − q/b  (p=0.5, q=0.5, b=asymmetry_ratio); f*<0 → 0

def parse_pct(value) -> float | None              # '-30%' → 0.30 (절대 fraction)
def extract_asymmetry_ratio(asym: dict) -> tuple[float | None, str | None]
def size_one(candidate, cfg, portfolio_total_krw, drawdown_brake_active) -> SizeRecommendation
def apply_portfolio_kelly_cap(recs, cfg) -> list[str]   # 합산 초과 시 비례 축소
```

`size_one` 파이프라인: asymmetry guard → kelly → half-size 분기 → per-position cap → min floor → drawdown brake.

## Cap / Guard (thresholds.yaml 설정)

| guard | thresholds.yaml 키 | 값 | 동작 |
|---|---|---|---|
| 단일 25% cap (G16) | `sizing.per_position.max_pct` | 0.25 | 초과 시 clamp |
| 최소 진입 floor | `sizing.per_position.min_pct` | 0.02 | 미만 → `verdict="rejected_low_asymmetry"` |
| 합산 Kelly 0.5 (G16) | `sizing.kelly.portfolio_kelly_cap` | 0.5 | 비례 축소 |
| fractional Kelly | `sizing.kelly.fraction` | 0.25 | quarter-Kelly (doctrine 1/4~1/2) |
| asymmetry guard (G5) | `thesis.asymmetry.min_ratio` / `half_size_below_ratio` | 2.0 / 3.0 | ratio<min → half-cap; ratio<half_below → size 절반 |
| drawdown brake (G17) | `sizing.drawdown_brake.threshold_pct` | 0.15 | brake active 시 size 절반 |
| cash-band block (G18) | (macro `cash_band[0]`) | — | `current_cash_pct < cash_band[0]` → `blocked_cash_band` |

## SizeRecommendation.verdict

`size_recommended` / `size_recommended_half_cap` / `rejected_low_asymmetry` / `rejected_no_user_context` / `blocked_drawdown_brake` / `blocked_cash_band` / `needs_user_decision`

## Portfolio context 의존 (G12)

`application/sizing._portfolio_context_from_yaml(date)` 우선순위:
1. `config/user/portfolio.yaml` 명시 override
2. 자동 파생 `_account/derived-{date}.json`
3. fallback (drawdown 0, cash None)

**`total_capital_krw` 는 manual-only** — `portfolio.yaml` 부재 시 `None` 반환 → `recommendations: []` + `blocked_reason` (G12). 근거: `sizing.requires_user_input.portfolio_context: true`.

## Macro regime sizing budget

`_load_macro_regime(date)` 가 `00-macro-regime.json` read → `cash_band` (default `[0.30, 0.70]`) + `regime_decision.regime`. `cash_band[0]` 이 G18 floor.

## 산출물 schema

`05-sizing-recommendation.json`:
- `recommendations: [asdict(SizeRecommendation)...]`
- `portfolio_context` — `regime` / `cash_band` / `drawdown_brake_active` / `cash_band_violation`
- `stats` — `total` / `by_verdict` / `portfolio_kelly_notes`
