# ADR-0001 — Deployment residency = 로컬 primary

`status: Accepted`
`date: 2026-06-06`
`refs: G9, specs/deployment-residency.md`

## Context

한국 금융 API (DART OPEN API · KIS Open Trading API · KRX data) 는 해외/클라우드
데이터센터 IP 에서 인증·조회 자체가 불가능하다 (DART 503 / KIS TCP timeout / KRX 403,
관측 2026-05). 따라서 daily 파이프라인의 실행 위치는 자유 선택지가 아니라 제약이다.

## Decision

Primary deployment = **로컬 (launchd macOS / systemd Linux) + Korean residential ISP**.
cloud routine 은 KIS/DART/KRX 를 호출하지 않고 IP-residency 무관 출처(Yahoo/FRED)만 쓰는
stage 에 한해서만 허용. crontab 등 시스템 cron 금지 — 모든 자동화는 launchd LaunchAgent.

본 ADR 은 **포인터** 다. 전체 spec (관측 데이터 표 · fallback 3조건 · 재활성 조건) 과
*결정 우선순위* 는 [`specs/deployment-residency.md`](../specs/deployment-residency.md) 에
있고, 그 spec 은 스스로 "CLAUDE.md / hard-guards.md / 모든 deployment 결정의 상위" 라고
선언한다 (헌법성 spec). ADR 레지스터는 그 결정을 ledger 에 등록만 한다.

## Consequences

- `applications/cloud_routine_run.sh` deprecated (첫 줄 `exit 1`).
- 스케줄 SSoT = `governance/schedules.yaml` → `infrastructure/scheduling/*` 가 plist emit.
- KIS/DART/KRX IP 정책 변경 시에만 cloud 재활성 (spec §5 조건).

## Alternatives considered

- **Cloud-primary (Anthropic Routines daily)** — 기각. DART/KIS IP 차단으로 daily stage
  실행 불가. fallback §3 조건을 daily 가 위반.

## Supersedes / Superseded-by

(없음)
