# resolver — metric_path 화이트리스트

## 신규 metric 추가 절차

1. **`rules/resolver.py` 에 `register_metric` 분기 추가**:
   ```python
   @register_metric("my_new.metric")
   def _my_new(snapshot: TickerSnapshot, ctx: MetricContext) -> float:
       ...
   ```
2. **TickerSnapshot 의 derived 메서드 호출** (산술 계산은 domain 객체 책임 — G6).
3. **unit test 의무**: `domains/screener/tests/unit/test_screener_resolver.py` 에 정상 / data_missing / 경계 case.
4. **profile YAML 에 사용**: `rules/leaf.py` 의 `ThresholdRule` 또는 `ScoringRule` 의 `metric_path: "my_new.metric"`.

## 절대 금지 패턴

```python
# ❌ dynamic eval — YAML 이 표현식 DSL 로 미끄러질 통로
return eval(expression, snapshot.__dict__)

# ❌ getattr 로 dynamic attribute lookup
return getattr(snapshot, dynamic_attr_name)

# ❌ exec / compile
```

위 패턴은 G13 우회 risk + 백테스트 결정론 불가. 신규 metric 의 PR 마찰은 의도된 안전벨트.

## 등록된 metric (PR2 시점)

| metric_path | 반환 | period_years | tax_rate |
|---|---|---|---|
| `annuals_avg.roic` | 최근 N년 ROIC 평균 | 필수 | 필수 |
| `ttm.fcf_to_revenue` | TTM FCF / Revenue | — | — |
| `latest_annual.debt_to_equity` | D/E (가장 최근) | — | — |
| `latest_annual.interest_coverage` | 이자보상배율 (가장 최근) | — | — |
| `fcf_positive_years` | 최근 N년 중 FCF 양수 연도 수 | 필수 | — |
| `signals.count` | capital_allocation_signals 갯수 | — | — |

## data_missing 처리

`InsufficientHistoryError` / `MetricResolutionError` 는 `ThresholdRule.evaluate` / `ScoringRule.evaluate` 가 catch 해 `RuleResult(passed=False, reasons=("data_missing: ...",))` 반환. caller (composite) 는 fail 처럼 처리.

snapshot 자체가 `None` (cache miss) 인 경우는 `run_screen` 의 단계에서 `ScreenVerdict(verdict='unknown')` 으로 분류 — resolver 가 호출되지 않음.
