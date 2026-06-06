# ADR-0006 — Fat-contract ISP: `EnrichCutoffProfile` 단일 정책 단위

`status: Accepted`
`date: 2026-06-06`
`refs: D-ARCH-2, 0004, domains/_shared/profile_registry/schema.py`

## Context

`EnrichCutoffProfile` = {required_enrichments, cutoff_rules, version, provenance}. universe 는
사실상 `required_enrichments` 만, screener 는 `cutoff_rules` 만 소비하는데 둘 다
프로파일 *전체* 에 의존한다. ISP (Interface Segregation) 관점에서 "universe-view /
screener-view 로 쪼개야 하나" 가 제기됐다.

## Decision

**쪼개지 않는다 — 통째 의존 유지.** 프로파일은 enrich+cutoff 를 *한 호흡으로* 정의하는
**단일 정책 단위** 이고, 통째 의존이 그 의도를 정직하게 반영한다. 한 종목의 "무엇을 enrich
해야 하고, 그 결과를 어떤 cutoff 로 거르나" 는 분리할 수 없는 한 정책이다.

screener 의 cutoff 단계가 universe 의 `required_enrichments` 를 역참조해 입력 완전성을
판단하는 **completeness gate** 는 이 단일 단위에서 비롯한 *의도된 결합* 이다 (모듈 경계
위반이 아니라 명시적 입력-완전성 게이트). 누락 enrichment 종목은 `verdict="caution"` 분기.

## Consequences

- serde 분할 비용 > ISP 이득 (특히 profile_registry cutover 대기 중) — 분할 보류.
- 본 결정의 *계약 본문* 은 `domains/_shared/profile_registry/schema.py` docstring 과
  `pipeline-overview.md` §4b 에 있다 (그쪽은 HOW/계약, 본 ADR 은 WHY/대안 기록).

## Alternatives considered

- **profile 을 universe-view / screener-view 로 ISP 분할** — 기각. 단일 정책 단위 의미
  훼손 + serde 분할 비용. (cutover 후 재평가 여지.)

## Supersedes / Superseded-by

(없음)
