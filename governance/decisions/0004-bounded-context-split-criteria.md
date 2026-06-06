# ADR-0004 — BC 통폐합 기준: 수직 병합 기각, screener/universe 분리 유지

`status: Accepted`
`date: 2026-06-06`
`refs: D-ARCH-2, 0006, pipeline-overview.md §4b`

## Context

`universe` (Stage 1 *enrich*) 와 `screener` (Stage 2 *cutoff*) 는 한 파이프라인 단계
연쇄라 "한 BC 로 병합하면 더 단순하지 않나" 가 반복 제기됐다. 더 일반적으로 — "두 모듈을
합쳐야 하나 / 쪼개야 하나" 판단 기준이 없었다.

## Decision

**분리 유지.** 기준은 컴포넌트 응집 원칙 (CCP / CRP):

- **CCP (함께 변하면 함께 산다)** — universe(per-source fan-out enrich) 와 screener(rule
  tree cutoff) 는 IO shape · 타이밍 · 카디널리티가 다르고 *함께 변하지 않는다*. 한 BC 로
  묶으면 한쪽 변경이 다른 쪽을 흔든다.
- 공통 관심사 (enrich+cutoff 를 한 정책으로 보는 `EnrichCutoffProfile`) 는 BC 병합이 아니라
  `_shared` 계약으로 **hoist** 했다.

2026-06 구조 리뷰의 관통 결론: **whole-BC 수직 병합 추천 0 건.** 경계 *자체* 는 건전하고,
잔여 finding 은 미완 cutover 에 몰려 있다.

## Consequences

- 경계는 `01-universe.json` 단방향 파일 핸드오프로 유지.
- screener 가 universe 의 `required_enrichments` 를 역참조하는 **completeness gate** 는
  병합이 아니라 *의도된 cross-domain 결합* — 그 단일 정책 단위 근거는 [ADR-0006].
- 이 판단이 "이 모듈 합쳐/쪼개야 하나" 의 일반 원칙으로 → [D-ARCH-2].

## Alternatives considered

- **universe+screener 수직 병합** — 기각. 변경축 상이 → CCP 위반, 회귀 영향 폭발.
- **per-source 마이크로 BC 분할** — 기각. 과분할, 공통 계약 중복.

## Supersedes / Superseded-by

(없음)
