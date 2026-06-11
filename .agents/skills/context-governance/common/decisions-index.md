# Decisions — ADR (Architecture Decision Records)

> **원본**: `governance/decisions/0001-*.md` ~ `0011-*.md` (11파일)
> **본 파일**: agent-readable 인덱스. append-only ledger — 기각(`Rejected-proposal`)도 영구 보존.

| ADR | 제목 | Status | 핵심 결정 |
|---|---|---|---|
| 0001 | Deployment residency = 로컬 primary | Accepted | KIS/DART/KRX IP 제약 → 로컬 KR ISP primary. cloud 는 Yahoo/FRED 만 |
| 0002 | governance/config 분리 = 소유·버전관리 축 | Accepted | 파일 포맷 아닌 소유/버전관리 축으로 분리. `runtime-policy.yaml` 은 governance/ 잔류 |
| 0003 | 결정론 계산 LLM 위임 금지 | Accepted | G6: 모든 정량 계산은 Python. LLM draft 만, commit 은 결정론 gate |
| 0004 | BC 통폐합 기준 | Accepted | screener/universe 분리 유지. CCP·CRP 기준 — 함께 변하면 함께, 다르면 분리 |
| 0005 | `_boundary` = 유일 infra-import 게이트 → typed adapter factory | Accepted | `_boundary.py` 단일 게이트 + narrow Protocol port 주입 패턴. god-module → adapter factory |
| 0006 | Fat-contract ISP: `EnrichCutoffProfile` 단일 정책 단위 | Accepted | enrich+cutoff 를 한 호흡으로 — 분리하지 않음. ISP 분할보다 단일 정책 의미 우선 |
| 0007 | risk_engine: 물리 concern 서브패키지 reorg | **Rejected** | 2D 디렉토리 복잡도 > 이득. flat 모듈 유지. 재제안 방지 기록 |
| 0008 | Storage topology: 재생성 가능성·수명·소유 축 | Accepted | `operations/`(휘발) / `telemetry/`(재생성-불가 증거) / `.cache/`(재생성 가능) |
| 0009 | Claude Code → Zed Agent 마이그레이션 | Accepted | `.claude/skills/` → `.agents/skills/`. hook 전면 파기, inject_session_state 만 Python 재구현 |
| 0010 | Hook Disposition | Accepted | 8개 hook 중 7개 파기. `inject_session_state` 만 `bootstrap_context.py` 로 이관 |
| 0011 | Agent Harness Remediation v4 | Accepted | Skill-First Context Injection. `domains/` BC 문서 → `skills/context-{bc}/` 흡수. 100줄 하드캡 |

## 우선순위

- ADR-0009 + 0010 + 0011: 현재 아키텍처의 기본 골격 — 작업 시 가장 자주 참조
- ADR-0003 + 0005: G6 / DDD 경계 enforcement — 일상적 코딩 시 참조
- ADR-0004 + 0006 + 0007: BC 경계 / 프로파일 구조 — 신규 BC 추가 검토 시 참조
- ADR-0001 + 0002 + 0008: 배치 / 설정 / 저장소 — 환경 설정 변경 시 참조
