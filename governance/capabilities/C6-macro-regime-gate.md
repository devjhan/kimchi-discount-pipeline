# C6 — macro regime gate

## Job Story

> **When** 새 거래일이 시작될 때,
> **I want** regime 분류(early / mid / late / crisis / unknown)에 따른 cash band 를,
> **so I can** 생존을 우선으로 그날의 총노출 budget 을 결정한다.

제약 계층의 L1 (생존 / Macro Regime). regime 이 cash band 를 정하고, 그 band 가 하류
sizing(C5)의 budget 이 된다.

## End-to-end trace

```
goal     "지금 시장 국면에서 얼마나 노출해도 되나" 의 상한(cash band)을 결정론으로 산출
trigger  일별 시작
stages   0a breadth_fetch  SPX 200d 비율 (Yahoo public chart)
         0  macro_regime    FRED(yield curve/credit spread/VIX %ile) + breadth → 결정론 분류
         (옵션) stage0 narrative skill — 자연어 narrative만, numeric 분류 절대 불변
input    config/signals/macro/breadth.yaml (manual breadth) + FRED API
output   operations/{date}/00-macro-regime.json (+ 00-macro-regime-narrative.md)
downstream  cash band → Stage 5 sizing(C5) total exposure budget
```

## 적용 axiom

- **#1 생존** — regime 별 cash band 로 노출 상한. crisis = 현금 비중 ↑.

## 성공 / 실패 신호

- ✅ 성공: 결정론 numeric 분류 + LLM 은 narrative 만(숫자 불변).
- ❌ 실패: `regime=unknown` 인데 임시로 `mid` 가정(fail-open 분기) · LLM 이 분류 numeric 변경.

## 관련

- BC: [`../../domains/macro/AGENTS.md`](../../domains/macro/AGENTS.md)
- skill: `investment-stage0-regime-labeler` (narrative only)
- 결정론↔LLM 경계: [ADR-0003](../decisions/0003-llm-drafts-python-commits.md)
- ergodicity / 생존 본문: [`../AXIOMS/ergodicity.md`](../AXIOMS/ergodicity.md)
