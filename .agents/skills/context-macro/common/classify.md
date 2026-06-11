# classify_regime — Voting Algorithm

## 알고리즘

1. `classify_regime` 이 `indicators` dict 를 순회 — 각 indicator 이름으로 `SIGNALS` registry 에서 Signal 을 조회해 `Signal.vote(result, thresholds)` 호출 → vote ∈ {crisis / late_cycle / mid_cycle} 또는 None (skip; value/percentile=None 또는 임계 gap)
2. 모든 vote 가 None 이면 regime="unknown" 반환
3. 비-None vote 들 중 **max severity 채택** (priority: crisis=3 > late_cycle=2 > mid_cycle=1 > early_cycle=0)
4. 각 vote 의 rationale (Signal.vote 가 함께 반환) 보존 + vote_summary 에 {regime: count}

## 코드 single source

vote 로직은 각 `Signal.vote` (`signals/{name}.py`) 가 소유. `classify_regime` (`application/regime_classify.py`) 은 registry 조회 + max-severity **aggregation** 만 담당 — main.py / 외부 LLM skill 어디에서도 vote 재구현 금지 (G6).

## detect_regime_shift

- 어제부터 require_consecutive_days+5 일 이전까지 backward scan
- 각 일의 `00-macro-regime.json` 의 `regime_decision.regime` 추출
- current_regime 과 다르면 stop, 같으면 consecutive++
- `consecutive >= require_consecutive_days and previous_regime != current_regime` → `alert=true`

## envelope `regime_decision` 필드 schema

```jsonc
"regime_decision": {
  "regime": "mid_cycle",         // 5 candidates
  "rationale": ["yield_curve=0.50 > 0 (non-inverted)", ...],
  "votes": ["mid_cycle", "mid_cycle"],     // skip 된 indicator 제외
  "vote_summary": {"mid_cycle": 2}
}
```
