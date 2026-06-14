# ADR-0015 — config 배치 판별 기준: cross-cutting 정책계약 vs BC-local 운영 vs 사용자 결정

`status: Accepted (구현 완료 2026-06-14)`
`date: 2026-06-14`
`refs: 0002 (ownership axis), 0013, 0014, D-ARCH-1, G14, domains/*/config/, config/user/`

## Context

ADR-0002 는 governance vs config 의 분리축을 **소유/버전관리** (developer doctrine =
git-tracked governance/ vs 사용자 override = gitignored config/) 로 정의했다. 그러나
"어떤 config 가 어디 사느냐" 에 대한 *두 번째 축* 은 명시되지 않아, 상반된 두 마이그레이션이
공존하게 됐다:

- **Runs 2/7**: 정책 임계값을 monolithic `governance/thresholds.yaml` *밖으로* 꺼내
  per-BC config 로 분산 (`macro/config/regimes.yaml`, `catalyst/config/detectors.yaml`,
  `universe/config/*`). 동기: locality — 임계값이 그것을 소비하는 BC 코드 옆에.
- **ADR-0013**: screener 의 엔진-내부 config (`domains/screener/config/`) 를 *governance/* 로
  중앙화. 동기: 정책↔메커니즘 *계약* 의 단일 SSoT + 버저닝/provenance/drift.

표면적으로 모순("screener 는 config 없는데 macro/catalyst/universe 는 있다")이지만, 실은
판별축이 한 개 더 있다. 본 ADR 이 그 축을 명시해 회귀(잘못된 일괄 이동)를 막는다.

## Decision

config 배치는 **두 직교 축**으로 결정한다:

1. **소유 축 (ADR-0002 — 누가 편집/버전관리하나)**
   - developer doctrine → git-tracked
   - 사용자/배포 override → gitignored (`*.local.yaml`, `config/user/`, `config/signals/`)

2. **결합 축 (본 ADR — fan-out + 계약성)**
   - **cross-cutting 정책계약**: ≥2 BC 가 소비 + 정책↔메커니즘 *계약* + 버저닝/provenance/
     drift/audit 필요 → **`governance/policy/`**.
     예: screener profiles/strategies/hard_guards (universe enrich + screener cutoff 공유,
     `vN.yaml` 레지스트리). [ADR-0013/0014]
   - **single-BC 운영 config**: 한 BC 만 소비 + plugin manifest(어떤 adapter/source/detector
     를 instantiate) + 그 BC 전용 임계값. cross-BC 계약·버저닝 불요 → **`domains/<bc>/config/`**.
     예: universe `sources.yaml`/`enrichers.yaml`, macro `regimes.yaml`, catalyst `detectors.yaml`.
   - **사용자/운영자 결정**: developer doctrine 도 mechanical wiring 도 아닌, 배포·사용자별
     판단 → **`config/user/`** (gitignored live + `.example` tracked, graceful-absent 로드).
     예: portfolio.yaml, behavior.yaml, **manual_additions.yaml, exclusions.yaml** (G14 universe
     멤버십 — 본 ADR 에서 `domains/universe/config/` → `config/user/` 이전).

판별 순서: ① 사용자 결정인가? → `config/user/`. 아니면 ② cross-cutting 정책계약 +
버저닝 필요한가? → `governance/policy/`. 아니면 ③ single-BC 운영 → `domains/<bc>/config/`.

### 두 마이그레이션의 화해
- Runs 2/7 은 옳다 — regime/detector 임계값은 single-BC 운영 config (축 2-b). thresholds.yaml
  monolith 에서 빼 locality 확보한 것은 본 기준과 정합.
- ADR-0013 도 옳다 — screener profiles 는 cross-cutting 정책계약 (축 2-a). 엔진 내부에 있던 게
  anomaly 였다.
- 둘은 "모든 정책은 governance" 라는 (틀린) 단일 규칙이 아니라, 본 판별 기준 하에 *각각 옳은*
  배치다. → single-BC config 를 governance 로 일괄 이동하는 것은 **금지** (mechanical wiring 을
  doctrine 으로 격상하는 오류).

## Consequences

- **manual_additions / exclusions 이전 (구현):** `domains/universe/config/` →
  `config/user/{manual_additions,exclusions}.yaml` (gitignored) + `.example` (tracked).
  로더: `_boundary.load_user_config(filename)` → `utils.load_user_config_optional`
  (graceful `{}`). sources.yaml 의 manual_addition entry 는 `user_items_ref:` (config/user)
  로 참조 — BC-config 참조용 `items_ref:` 와 명시 구분. `load_sub_config` 은 BC-local
  reference data (subsidiaries/preferred_pairs) 전용으로 의미 narrowing.
- **deterministic guard:** `domains/<bc>/config/` 밑에 정책계약 schema(`policy-profile-v1` /
  `segment-def-v1` / `segment-concept-v1`)가 등장하면 build fail (정책계약이 BC config 로
  새는 회귀 차단) — `tests/architecture/test_policy_consolidation.py`.
- **subsidiaries.yaml / preferred_pairs.yaml 은 잔존** — reference SSoT data (축 2-b), 사용자
  결정 아님. 이전하지 않는다.
- **잔여 판단여지:** macro `regimes.yaml`·catalyst `detectors.yaml` 는 plugin manifest(wiring)와
  임계값(policy-ish)이 한 파일에 동거한다. single-BC 소비라 현 위치 유지가 옳으나, 만약 향후
  ≥2 BC 가 같은 임계를 소비하게 되면 축 2-a 로 재평가 (rule-of-three).

## Alternatives considered

- **모든 정책/임계값 → governance 일괄 중앙화.** 기각 — single-BC wiring 을 doctrine 으로
  격상, locality 상실, Runs 2/7 의도 역행.
- **manual_additions/exclusions git-tracked 유지 (domains/universe/config).** 기각 — 사용자
  universe 멤버십은 배포/사용자별 결정 (축 1 override). 단, 1인 personal-research 도구라
  git-tracking 도 방어 가능했음 — config/user 관례 일관성 위해 override 채택.

## Supersedes / Superseded-by

- **Extends** ADR-0002 — 소유 축에 결합 축(fan-out + 계약성)을 직교 추가.
- **Generalizes** ADR-0013/0014 — screener 중앙화를 "cross-cutting 정책계약" 일반 기준의 한 사례로 위치.
- Supersede 없음 (append-only).
