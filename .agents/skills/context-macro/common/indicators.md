# Signals — vote-in-signal Plugins

## Signal ABC

```python
class Signal(ABC):
    name: str  # registry key = cfg['thresholds'] 하위키 = indicators dict 키 (3 일치)

    def fetch(self, env, date) -> tuple[IndicatorResult, list[str]]: ...
    def vote(self, result, thresholds) -> tuple[str, str] | None: ...  # (regime, rationale) | None
```

`env` 부재 / fetch 실패 시 `empty_indicator(reason)` (`value=None`, `skip_reason=…`) + warnings append. `vote` 는 `value`/`percentile` None 이면 None 반환 → classify 가 graceful 제외.

## Registry

```python
SIGNALS: dict[str, type[Signal]] = {}

def register_signal(name: str):
    def deco(cls):
        SIGNALS[name] = cls  # dup → 덮어쓰기 (silent override 주의)
        return cls
    return deco
```

## Factory

```python
def build_signals(cfg: dict) -> dict[str, Signal]:
    # cfg['signals'] 리스트 순회 → SIGNALS registry lookup → 인스턴스화
    # 등록되지 않은 signal name → ValueError
```

`factory.py` 의 top-level import 들이 각 signal 모듈을 로드 → `@register_signal` 부작용 트리거.

## 4 Signal 플러그인 상세

| Signal | fetch 상세 | vote 상세 |
|---|---|---|
| `yield_curve` | FRED DGS10, DGS2 latest 값; DGS10 - DGS2 spread 계산 | spread ≤ crisis_signal → crisis; ≤ late_cycle_signal → late_cycle; else mid_cycle |
| `credit_spread` | FRED BAMLH0A0HYM2 latest OAS | OAS ≥ crisis_min → crisis; ≥ late_cycle_min → late_cycle; ≤ mid_cycle_max → mid_cycle |
| `vix` | FRED VIXCLS latest + 5y history → `_stats.percentile(history, latest)` | percentile ≥ panic_min → crisis; ≤ complacent_max → late_cycle |
| `breadth` | breadth.yaml (Stage 0a prefetch) 로드만 (무거운 fan-out 은 `breadth_fetch.py`) | pct ≤ crisis_max → crisis; ≤ late_cycle_max → late_cycle; ≥ healthy_min → mid_cycle |

## 신규 indicator 추가 절차

1. `signals/{name}.py` 에 `@register_signal("{name}")` Signal 서브클래스 (fetch + vote)
2. `signals/factory.py` 에 import 한 줄 추가 (등록 트리거)
3. `config/regimes.yaml` 의 `signals:` 리스트에 `{name}` + `thresholds:` 에 임계값
4. (가능하면) `audit/citation.py` 의 citation 형식 검증

`main` / `classify_regime` 는 건드리지 않는다.

## Over-abstraction 경계 (하지 말 것)

- voting aggregation (max-severity) 의 `VotingStrategy` ABC 화 — max-severity 는 1번 사상 doctrine, rule-of-three 미충족
- regime enum / severity 의 config 화 — doctrine·거의 불변, drift 위험
- LLM narrative 의 ports 화 — numeric label 은 LLM-free 가 hard rule
