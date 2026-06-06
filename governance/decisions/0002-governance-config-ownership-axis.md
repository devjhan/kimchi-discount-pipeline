# ADR-0002 — governance/config 분리 = 소유·버전관리 축 (파일 포맷 아님)

`status: Accepted`
`date: 2026-06-06`
`refs: D-ARCH-1, G9, procedures/config-files-reference.md`

## Context

루트에 `config/` · `secrets/` 가 신설된 뒤 "그러면 `governance/runtime-policy.yaml` 등
machine-read yaml 도 `config/` 로 옮겨야 하지 않나" 라는 제안이 반복 제기됐다. 표면적으로는
"yaml 은 config 폴더에" 가 깔끔해 보인다.

## Decision

**기각 — 현 배치 유지.** 시스템의 분리축은 *파일 포맷* (yaml vs md) 이 아니라
**소유/버전관리 축** 이다:

- **개발자 doctrine** = git-tracked `governance/*.yaml` + `governance/*.md` (헌법. 둘 다
  버전관리되므로 markdown 과 machine-read yaml 의 *의도적 동거* 가 맞다).
- **사용자/배포 override** = gitignored `*.local.yaml` (deep-merge) + `config/user/` +
  `config/signals/`.

`runtime-policy.yaml` 은 G9 정적 enforcement (`block_auto_trade` · KIS read-only whitelist,
헤더가 "사용자 임의 변경 금지") 다. 이를 사용자 편집 가능한 `config/` 로 옮기는 것은
**가드를 노브로 강등하는 보안 후퇴**다.

## Consequences

- 배포별 조정 need 는 `runtime-policy.local.yaml` deep-merge (`load_runtime_policy()`,
  local 우선) 로 *이미* 충족 — relocation 불요.
- 이 결정이 "이 config/문서는 governance 냐 BC 산하냐 / 루트 config 냐" 판단의 일반
  원칙으로 일반화됐다 → [D-ARCH-1](../directives/05-architecture.md).
- 관련: seed credential 은 dotenv-at-root 관례를 따라 `.env` (구 `.env.agents` rename 완료).

## Alternatives considered

- **`governance/*.yaml` → `config/` 이전** — 기각 (위). 소유축을 포맷축으로 오인 + G9
  가드 강등.

## Supersedes / Superseded-by

(없음)
