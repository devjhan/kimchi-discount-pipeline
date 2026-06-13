---
name: context-governance
description: Investment 파이프라인 governance/ 규범적 규칙 주입. common/ 인덱스 파일을 통해 directives/capabilities/decisions/proposals/AXIOMS/thresholds 조회 경로 제공. 작업 전 invoke 권장.
---

# context-governance

`governance/` 디렉토리의 규범적 규칙(SSoT)을 agent 컨텍스트로 주입하는 인덱스 스킬. 작업 성격에 따라 필요한 하위 인덱스만 선행 읽기. `governance/` = Layer 1 (규칙), `.agents/skills/` = Layer 2 (agent 컨텍스트 뷰).

## 선행 읽기

| 작업 | 읽을 파일 | 원본 |
|---|---|---|
| 코딩 컨벤션 (D-ID) | `common/directives-index.md` | `governance/directives/` |
| 파이프라인 기능 정의 | `common/capabilities-index.md` | `governance/capabilities/` |
| 아키텍처 결정 이력 | `common/decisions-index.md` | `governance/decisions/` |
| 제안 draft 검토 | `common/proposals-index.md` | `governance/proposals/` |
| 5대 철학 | `common/axioms-index.md` | `governance/AXIOMS/` |
| 정량 임계값 | `common/thresholds-index.md` | `governance/thresholds.yaml` |

## 핵심 불변식

- **우선순위: AXIOMS > G1-G22 > D-ID** — 충돌 시 상위 rule 우선
- **governance/ = SSoT** — 본 skill 의 `common/` 파일은 agent-readable 뷰. 충돌 시 `governance/` 원본 우선
- **ADR append-only**: `governance/decisions/NNNN-*.md` 로 영구 기록, 기각(`Rejected-proposal`)도 보존
- **_boundary.py 단일 게이트**: 모든 BC 의 infra import 는 `_boundary.py` 만 허용

## governance/ 디렉토리 구조

| 디렉토리 | 성격 | 내용 |
|---|---|---|
| `AXIOMS/` | 철학 (why) | 5대 철학 — 생존·반증·엣지·비대칭·통계정직 |
| `directives/` | 코딩 컨벤션 (how) | D-CORE / D-ARCH / D-PY / D-CFG / D-Q / D-SEC |
| `decisions/` | ADR (why this decision) | 0001~0013, append-only ledger |
| `capabilities/` | 기능 정의 (what) | C1~C6 Job Story → End-to-end trace |
| `proposals/` | 제안 draft | ADR 승격 전 staging, 자유 수정 |
| `procedures/` | 절차 참조 | config-files-reference.md |
| `policy/` | 정책 전 tier 단일 부모 (ADR-0013) | profiles / segments / concepts / segment_profiles / global |
| `policy/profiles/` | per-ticker 정책 (scope=ticker) | Enrich-Cutoff profile (runtime data) |
| `policy/segments/` `policy/concepts/` `policy/segment_profiles/` | segment 정책 (subset scope) | ADR-0012 — selector + concept anchor + named 정책 |
| `policy/global/` | global 정책 (whole-universe scope) | strategies / profiles / hard_guards.yaml (구 `domains/screener/config/`) |
| `thresholds.yaml` | 정량 SSoT | thesis·sizing·statistics·falsifier·enforcement |
| `schedules.yaml` | 일정 | 파이프라인 cron schedule |
| `runtime-policy.yaml` | 실행 정책 | G9 자동매매 차단 등 static enforcement |
| `deployment-residency.md` | 배치 | 로컬 KR ISP primary deployment |
| `pipeline-overview.md` | 개요 | Stage 0→6 파이프라인 전체 구조 |

> **정책 계층 통합 (ADR-0013, 구현 완료 2026-06-13)**: per-ticker(`policy/profiles/`) · segment(`policy/segments|concepts|segment_profiles/`) · global(`policy/global/`, 구 `domains/screener/config/`) 전 tier 가 `governance/policy/` 산하로 이전됨 + `scope∈{global,segment,ticker}` tagged 단일 `policy-profile-v1` 스키마로 수렴. per-ticker→leaf segment 추상화는 *보류*(Q3). global cutoff *평가* 는 여전히 screener `RuleFactory` 소유(스토리지만 이동, 엔진 통합 아님).

## Out of Scope

- `governance/policy/profiles/` — per-ticker runtime policy data (`/context-policy` + `/policy-profiler` 책임)
- `domains/` BC 내부 코드 — 각 `/context-{bc}` skill 참조
- 실제 governance rule 변경 — 본 skill 은 read-only 컨텍스트 주입만
