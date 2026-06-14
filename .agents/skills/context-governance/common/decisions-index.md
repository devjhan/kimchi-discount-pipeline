# Decisions — ADR (Architecture Decision Records)

> **원본**: `governance/decisions/0001-*.md` ~ `0013-*.md` (13파일)
> **본 파일**: agent-readable 인덱스. append-only ledger — 기각(`Rejected-proposal`)도 영구 보존.

| ADR | 제목 | Status | 핵심 결정 |
|---|---|---|---|
| 0001 | Deployment residency = 로컬 primary | Accepted | KIS/DART/KRX IP 제약 → 로컬 KR ISP primary. cloud 는 Yahoo/FRED 만 |
| 0002 | governance/config 분리 = 소유·버전관리 축 | Accepted | 파일 포맷 아닌 소유/버전관리 축으로 분리. `runtime-policy.yaml` 은 governance/ 잔류. **→ ADR-0015 가 결합 축(fan-out+계약성) 직교 추가** |
| 0003 | 결정론 계산 LLM 위임 금지 | Accepted | G6: 모든 정량 계산은 Python. LLM draft 만, commit 은 결정론 gate |
| 0004 | BC 통폐합 기준 | Accepted | screener/universe 분리 유지. CCP·CRP 기준 — 함께 변하면 함께, 다르면 분리 |
| 0005 | `_boundary` = 유일 infra-import 게이트 → typed adapter factory | Accepted | `_boundary.py` 단일 게이트 + narrow Protocol port 주입 패턴. god-module → adapter factory |
| 0006 | Fat-contract ISP: `EnrichCutoffProfile` 단일 정책 단위 | Accepted | enrich+cutoff 를 한 호흡으로 — 분리하지 않음. ISP 분할보다 단일 정책 의미 우선 |
| 0007 | risk_engine: 물리 concern 서브패키지 reorg | **Rejected** | 2D 디렉토리 복잡도 > 이득. flat 모듈 유지. 재제안 방지 기록 |
| 0008 | Storage topology: 재생성 가능성·수명·소유 축 | Accepted | `operations/`(휘발) / `telemetry/`(재생성-불가 증거) / `.cache/`(재생성 가능) |
| 0009 | Claude Code → Zed Agent 마이그레이션 | Accepted | `.claude/skills/` → `.agents/skills/`. hook 전면 파기, inject_session_state 만 Python 재구현 |
| 0010 | Hook Disposition | Accepted | 8개 hook 중 7개 파기. `inject_session_state` 만 `bootstrap_context.py` 로 이관 |
| 0011 | Agent Harness Remediation v4 | Accepted | Skill-First Context Injection. `domains/` BC 문서 → `skills/context-{bc}/` 흡수. 100줄 하드캡 |
| 0012 | Segment-scoped profile 계층 + 벡터 semantic 분류 | Accepted | per-ticker·global 사이 *부분집합* profile tier 신설. `_shared/segment_registry`. rule+semantic(임베딩 cosine) 동급 selector. 벡터=telemetry sqlite-vec. `--use-segments` opt-in. 명세 검증으로 `vec_distance_cosine`(vec0 미사용) 채택 |
| 0013 | 정책 계층 통합: 전 tier governance/ 단일화 + scope-tagged 스키마 통합 (per-ticker→segment 보류) | Accepted (구현 완료) | **Q2 완료(2026-06-13)**: global(구 `domains/screener/config/`) → `governance/policy/global` 이전, 전 tier `governance/policy/` 산하 + `scope∈{global,segment,ticker}` tagged 단일 `policy-profile-v1` 스키마. global cutoff *평가* 는 여전히 screener `RuleFactory` 소유(스토리지만 이동). **Q3 보류**: per-ticker→leaf segment 추상화 — 합성 이득은 이미 `per_ticker_for` 주입으로 달성, degenerate-selector/퇴화/blast radius 비용 큼. **→ ADR-0014 가 저장 레이아웃을 scope-미러로 재구조화 (flat merge 대체)** |
| 0014 | 정책 저장소 scope-미러 재구조화 + 결정론적 policy contract (manifest + ruff + arch fitness) | Accepted (구현 완료 2026-06-14) | ADR-0013 의 flat-merge 결과(`global/`·`segment_profiles/`)를 scope-미러 트리로 재정렬: profile=`policy/profiles/<scope>/<key>/v<N>.yaml`(path↔scope 불변식), 멤버십=`segments/`, anchor=`concepts/`, 조합=`strategies/`(versioned), G13=`hard_guards.yaml`. 코드 SSoT 생성 `methods_manifest.yaml` + strict cutoff validator(commit 시점 reject) + arch fitness(layout/sync/contract) + ruff. cutoff `ne` op·환각 metric_path·dangling ref 가 build red. 엔진 결합 불변(golden parity). NamedProfileRegistry→SegmentProfileRegistry |
| 0015 | config 배치 판별 기준: cross-cutting 정책계약 vs BC-local 운영 vs 사용자 결정 | Accepted (구현 완료 2026-06-14) | ADR-0002 소유 축에 결합 축 직교 추가. ① 사용자 결정 → `config/user/`(gitignored+.example), ② cross-cutting+버저닝 정책계약 → `governance/policy/`(screener profiles), ③ single-BC 운영(plugin manifest+전용 임계) → `domains/<bc>/config/`(macro regimes·catalyst detectors·universe sources). Runs2/7(분산)·ADR-0013(중앙화) 화해 — 일괄 이동 금지. manual_additions/exclusions → config/user 이전(user_items_ref/load_user_config). guard: BC config 에 정책계약 schema 누출 시 build fail |

## 우선순위

- ADR-0009 + 0010 + 0011: 현재 아키텍처의 기본 골격 — 작업 시 가장 자주 참조
- ADR-0003 + 0005: G6 / DDD 경계 enforcement — 일상적 코딩 시 참조
- ADR-0004 + 0006 + 0007: BC 경계 / 프로파일 구조 — 신규 BC 추가 검토 시 참조
- ADR-0006 + 0012 + 0013: **정책(profile) 계층** — per-ticker / segment / global 3 tier + 통합 완료(0013). profile·segment 작업 시 필수 참조
- ADR-0001 + 0002 + 0008: 배치 / 설정 / 저장소 — 환경 설정 변경 시 참조
