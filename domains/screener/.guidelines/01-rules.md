# rules/ — Rule 트리 작성 규약

## 새 Rule subclass 추가 절차

1. **base Rule ABC 상속**: `rules/base.py` 의 `Rule` 을 상속. `name` property + `evaluate(snapshot)` 메서드 의무.
2. **frozen dataclass 강제**: `@dataclass(frozen=True)` — Rule 인스턴스는 immutable.
3. **factory dispatch 분기 추가**: `rules/factory.py` 의 `RuleFactory._from_dict` 에 새 rule type 분기 한 줄 추가. YAML `type:` 필드와 매칭.
4. **methods_manifest.yaml 갱신**: scoring method 신규 등록 시 `config/methods_manifest.yaml` 에 entry 추가.
5. **unit test 의무**: `domains/screener/tests/unit/test_screener_rules.py` 에 pass/fail/edge case 각 1+. composite 라면 children 평가 정합도 검증.

## 직접 생성 금지

```python
# ❌ 금지 — HardGuardWrapper 자동 wrap 우회
rule = AndRule(_name="x", children=(...,))

# ✅ 올바름
rule = RuleFactory.build_strategy(strategy_yaml, profiles, hard_guards, tax_rate=tax_rate)
```

test 코드도 예외 없이 factory 사용. 단 leaf Rule 의 단위 evaluate 검증은 직접 생성 OK (composite tree 가 아니라 평가 동작만 verify 할 때).

## WeightedSumRule invariant

- `children=((rule, weight), ...)` 의 weight 합 > 0 의무. 0 이면 `ValueError`.
- `pass_score` 는 [0.0, 1.0] — YAML 작성 시 검증 없음, 사용자 책임.
- 정상화된 weighted average 가 `pass_score` 이상이면 pass.

## RuleResult 직렬화

`RuleResult.reasons: tuple[str, ...]`, `children: tuple[RuleResult, ...]` 는 frozen. `dataclasses.asdict()` 가 tuple → list 자동 변환. JSON 직렬화는 `application/screen.verdicts_as_json` 통해.

## Hard guard 와 commute

`HardGuardWrapper` 는 factory 가 outer 로 자동 wrap. strategy/profile YAML 이 hard_guards.yaml 의 `guards[].name` 과 동일 rule name 을 선언하면 `HardGuardViolationError` (factory invariant 검사 단계). `03-hard-guards.md` 참조.
