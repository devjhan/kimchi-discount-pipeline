# hard_guards.yaml — strategy-agnostic 잠금 영역

## 본 파일의 책임

`config/hard_guards.yaml` 의 `guards[]` 는 어떤 strategy/profile 도 우회 못 하는 catastrophic floor 다. RuleFactory.build_strategy 가 항상 outer wrapper (`HardGuardWrapper`) 로 자동 wrap — strategy YAML 이 `guards.*` 영역을 직접 override 시도하면 `HardGuardViolationError`.

## guards 항목 변경 절차

ROIC < 0 같은 catastrophic floor 변경은 다음 모두 필요:

1. **governance/specs PR** — `hard-guards.md` 의 G-rule 본문에 사유 명시
2. **사용자 명시 ack** — PR 본문에 사용자 결정 인용 (해당 floor 가 왜 변경되어야 하는지)
3. **unit test 갱신** — `domains/screener/tests/unit/test_screener_rules.py` 의 hard guard test 케이스 동기화
4. **본 디렉토리 갱신** — 새 guard 의 사유를 본 파일에 추가

## locked_paths

`hard_guards.yaml.locked_paths: ["guards.*"]` — strategy/profile YAML 의 rule 트리에 `name == guards[].name` 인 entry 가 등장하면 invariant 위반. 본 잠금은 RuleFactory `_assert_no_hard_guard_override` 가 강제.

## 권장 guard 패턴

guards 는 leaf Rule (ThresholdRule) 만 사용 — 단순성 보존. composite / scoring 도 가능하나 잠금 영역에 복잡 트리를 두는 것은 KISS 위반.

```yaml
# ✅ 권장
- type: "threshold"
  name: "solvency_floor"
  metric_path: "latest_annual.interest_coverage"
  op: "ge"
  threshold: 1.5
  rationale: "이자 cover < 1.5 는 좀비. 어떤 valuation 도 무의미."

# ❌ 비권장 — guards 안에 복합 가중치는 의도 불명확
- type: "weighted_sum"
  name: "complex_floor"
  ...
```

## 현재 guards (PR2 시점)

| name | metric | threshold | rationale |
|---|---|---|---|
| `solvency_floor` | `latest_annual.interest_coverage` | ≥ 1.5 | 이자 cover < 1.5 좀비 차단 |
| `leverage_ceiling` | `latest_annual.debt_to_equity` | ≤ 2.0 | D/E 200% 초과 파산 risk |

신규 추가는 위 4 단계 절차 준수.
