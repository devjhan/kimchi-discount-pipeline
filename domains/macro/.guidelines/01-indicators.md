# Signals — vote-in-signal Plugins

## 패턴 (F-9)

각 indicator 는 `signals/{name}.py` 의 `Signal` 서브클래스 — **fetch + vote 를 한
클래스에 캡슐화**한다 (`@register_signal("{name}")` 로 registry 등록). universe
`DiscoverySource` / screener `Rule` 과 동형이되, macro 는 *vote-aggregation* (독립
fan-out 아님) 이라 screener Rule 의 **vote-in-signal** 모양이 정확하다 — 각 indicator
가 자기 임계값으로 스스로 vote.

## Signal 인터페이스

```python
class Signal(ABC):
    name: str  # registry key = cfg['thresholds'] 하위키 = indicators dict 키 (3 일치)

    def fetch(self, env, date) -> tuple[IndicatorResult, list[str]]: ...
    def vote(self, result, thresholds) -> tuple[str, str] | None: ...  # (regime, rationale) | None
```

`env` 부재 / fetch 실패 시 `empty_indicator(reason)` (`value=None`, `skip_reason=…`)
+ warnings append. `vote` 는 `value`/`percentile` None 이면 None 반환 → classify 가
graceful 제외.

## 4 Signals

| name | source | value_label | vote |
|---|---|---|---|
| `yield_curve` | FRED DGS10 - DGS2 | inverted / flat / steepening / steep | spread ≤ crisis_signal → crisis; ≤ late_cycle_signal → late_cycle; else mid_cycle |
| `credit_spread` | FRED BAMLH0A0HYM2 (BAML HY OAS) | tight / moderate / stress / crisis | OAS ≥ crisis_min → crisis; ≥ late_cycle_min → late_cycle; ≤ mid_cycle_max → mid_cycle |
| `vix` | FRED VIXCLS + 5y history → percentile | panic / elevated / normal / complacent | percentile ≥ panic_min → crisis; ≤ complacent_max → late_cycle |
| `breadth` | breadth.yaml (Stage 0a prefetch) | weak / soft / neutral / broad | pct ≤ crisis_max → crisis; ≤ late_cycle_max → late_cycle; ≥ healthy_min → mid_cycle |

> `breadth` 의 `fetch` 는 breadth.yaml 을 **로드만** 한다 — 무거운 500-ticker SPX
> fan-out 은 `breadth_fetch.py` (Stage 0a prefetch) 에 남긴다 (Signal.fetch 로 끌어오지 X).

## 신규 indicator 추가

1. `signals/{name}.py` 에 `@register_signal("{name}")` Signal 서브클래스 (fetch + vote)
2. `signals/factory.py` 에 import 한 줄 추가 (등록 트리거)
3. `config/regimes.yaml` 의 `signals:` 리스트에 `{name}` + `thresholds:` 에 임계값
4. (가능하면) `audit/citation.py` 의 citation 형식 검증

`main` / `classify_regime` 는 건드리지 않는다 — main 은 factory 로 fetch, classify 는
registry 로 vote 를 조회한다.

## Over-abstraction 경계 (하지 말 것)

- voting aggregation (max-severity) 의 `VotingStrategy` ABC 화 — max-severity 는 1번
  사상 doctrine, rule-of-three 미충족. `classify_regime` 의 단일 함수 seam 으로 충분.
- regime enum / severity 의 config 화 — doctrine·거의 불변, drift 위험.
- LLM narrative 의 ports 화 — numeric label 은 LLM-free 가 hard rule.
