# ADR-0008 — Storage topology: 재생성 가능성·수명·소유 축

`status: Accepted`
`date: 2026-06-06`
`refs: D-ARCH-1, 0002, procedures/config-files-reference.md`

## Context

저장소 디렉토리 분류에 오배치가 있었다 — 재생성 *불가* 증거 (`nav-history`, Σ 자회사
시총×지분율) 가 "재생성 가능 캐시" (`.cache/`) 에 섞이는 식. "어느 디렉토리에 무엇이 사는가"
판단 기준이 없었다.

## Decision

분류축은 *파일 포맷* 이 아니라 **재생성 가능성 + 수명 + 소유** 다:

| 디렉토리 | 축 | 내용 |
|---|---|---|
| `operations/{date}/` | 일별 휘발 · 재생성 가능 | Stage 0~6 산출물 + daily-brief |
| `telemetry/` | cross-day · **재생성-불가 증거** | audit / positions / nav-history / logs / policy_drafts |
| `.cache/` | 재생성 가능 (gitignore) | dart / financials 캐시 |
| `config/` | 사용자 입력 | user / signals |
| `secrets/` + `.env` | 자격증명 (gitignore, 0600) | API key |

핵심: `nav-history` 는 재생성-불가 증거이므로 `telemetry/` (캐시 아님). 경로는
`infrastructure/_common/utils.py` path helper 가 SSoT 로 계산 (env override seam).

## Consequences

- `.cache/` 는 언제든 삭제 가능 (재생성). `telemetry/` 는 삭제 = 증거 소실 (G20 append-only).
- 소유축 분리 ([ADR-0002]) 와 정합: `config/`(사용자) vs `governance/`(개발자) vs
  `telemetry/`(시스템 누적).
- 이 판단이 "이 산출/상태 파일 어디 두나" 일반 원칙으로 → [D-ARCH-1].

## Alternatives considered

- **포맷별 분류 (모든 json 을 한 곳)** — 기각. 진짜 축은 재생성 가능성·수명, 포맷 아님.

## Supersedes / Superseded-by

(없음)
