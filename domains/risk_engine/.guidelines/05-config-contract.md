# Config — central thresholds + runtime-policy (local config 없음)

risk_engine 은 **local `config/` 디렉토리가 없다** (universe 의 self-contained YAML 과 대조).
중앙 governance config 의 순수 consumer 이며, 자신이 mutate 하는 config 는 없다.

## 읽는 config

| 파일 | schema | 역할 | 로더 |
|---|---|---|---|
| `governance/thresholds.yaml` | `investment-thresholds-v1` (version 1) | sizing cap + asymmetry guard + proximity band + expiry tier (정량 SSoT) | `_boundary.load_yaml_config(args.config)` (default `DEFAULT_THRESHOLDS`) |
| `governance/runtime-policy.yaml` | `investment-runtime-policy-v1` (version 1) | G9 정적 enforcement (`block_auto_trade` / KIS read-only whitelist·blocklist) | `_boundary.kis_read_only_enabled()` → `load_runtime_policy()` (gitignore `runtime-policy.local.yaml` deep-merge) |
| `config/user/portfolio.yaml` | (user config, `.example` 추적) | `total_capital_krw` (manual) + drawdown/cash override | `_boundary.load_user_portfolio()` |
| `operations/{date}/00-macro-regime.json` | (Stage 0 산출) | `cash_band` / `regime_decision.regime` sizing budget | `application/sizing._load_macro_regime` (직접 json.load) |

## thresholds.yaml 키 (risk_engine 가 read)

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
    surface_in_brief: true
falsifier:
  proximity_bands: { low_max: 0.5, medium_max: 0.9 }
# statistics.* 는 thresholds.yaml 에 있으나 risk_engine 미사용 (audit_integrity 소비)
```

## 책임 분리

- **정량 임계값** (cap / ratio / band / tier) → `governance/thresholds.yaml` (cross-BC SSoT).
  risk_engine 은 read only, write 안 함.
- **G9 정책 스위치** (block_auto_trade / KIS whitelist) → `governance/runtime-policy.yaml`
  (정량 임계값과 분리 — 정책 변경 빈도/위험도가 다름).
- **per-position runtime state** (drawdown / cash) → derive 산출 (`_derived-{date}.json`),
  config 아님.

## D-CFG-1 공통 헤더

모든 governance YAML 은 `schema` / `version` / `description` / `last_updated` 보유 (D-CFG-1,
`block_anti_patterns` hook 강제). thresholds.yaml 은 comment banner + `version` / `last_updated` /
`schema` 보유.

## config-version 읽기 주의 (기록)

대부분 stage 는 `config.get("version", "unknown")` 으로 envelope `config_version` 채움. 단
`event_falsifier_linker` 는 `config.get("_meta", {}).get("version", "unknown")` 으로 읽는데
thresholds.yaml 은 top-level `version: 1` (no `_meta`) 이라 불일치 — 향후 정합화 대상.

## schema bump 규약

risk_engine 은 local config 가 없으므로 bump 규약은 **출력 envelope schema** 에만 적용:
payload shape 변경 시 `investment-stage5-sizing-v1` 등의 `vN` 을 올림. (입력 thresholds /
runtime-policy schema 변경은 해당 파일 소유자 governance 결정.)
