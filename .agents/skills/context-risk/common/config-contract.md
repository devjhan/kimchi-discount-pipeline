# Config — central thresholds + runtime-policy (local config 없음)

risk_engine 은 **local `config/` 디렉토리가 없다**. 중앙 governance config 의 순수 consumer.

## 읽는 config

| 파일 | schema | 역할 | 로더 |
|---|---|---|---|
| `governance/thresholds.yaml` | `investment-thresholds-v1` | sizing cap + asymmetry guard + proximity band + expiry tier (정량 SSoT) | `_boundary.load_yaml_config(args.config)` |
| `governance/runtime-policy.yaml` | `investment-runtime-policy-v1` | G9 정적 enforcement | `_boundary.kis_read_only_enabled()` |
| `config/user/portfolio.yaml` | (user config) | `total_capital_krw` (manual) + drawdown/cash override | `_boundary.load_user_portfolio()` |
| `operations/{date}/00-macro-regime.json` | (Stage 0 산출) | `cash_band` / `regime_decision.regime` | `application/sizing._load_macro_regime` |

## thresholds.yaml 키 (risk_engine read)

```yaml
sizing:
  kelly: { fraction: 0.25, portfolio_kelly_cap: 0.5 }
  per_position: { max_pct: 0.25, min_pct: 0.02 }
  drawdown_brake: { threshold_pct: 0.15, action: "halve_all_sizes", reset_threshold_pct: 0.05 }
  requires_user_input: { portfolio_context: true, output_size_without_input: false }
thesis:
  asymmetry: { min_ratio: 2.0, reject_below_min: false, half_size_below_ratio: 3.0 }
  expiry_alert:
    tiers: { notice_days: 90, warn_days: 30, expired_days: 0, overdue_days: -30 }
falsifier:
  proximity_bands: { low_max: 0.5, medium_max: 0.9 }
```

## 책임 분리

- **정량 임계값** → `governance/thresholds.yaml` (cross-BC SSoT). risk_engine 은 read only.
- **G9 정책 스위치** → `governance/runtime-policy.yaml` (정량과 분리)
- **per-position runtime state** (drawdown/cash) → derive 산출, config 아님

## D-CFG-1 공통 헤더

모든 governance YAML 은 `schema` / `version` / `description` / `last_updated` 보유.

## schema bump 규약

출력 envelope schema payload shape 변경 시 `investment-stage5-sizing-v1` 등의 `vN` 올림.
