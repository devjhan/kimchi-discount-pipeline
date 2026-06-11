# Graphify 플러그인 도입 ROI 분석 (2026-06-11)

> **성격**: Zed editor용 Graphify 플러그인(코드 의존성 그래프 시각화) 도입의 비용·편익·대안 분석. read-only findings — 설치·설정 plan 없음.
> **방법**: 프로젝트 구조(`_boundary.py` 패턴, cross-domain import, infrastructure 의존성) grep 실측 + 기존 정적 문서(mermaid/text diagram) 대조 + agent 혼선 사례(user report) 매핑.
> **핵심 질문**: Graphify의 auto-generated import graph가 (1) agent 혼선을 줄이는가, (2) 아키텍처 컴플라이언스 검증에 도움이 되는가.

---

## 0. 요약

| 축 | 판정 | 확신도 |
|---|---|---|
| **Agent 혼선 해소** | **낮음.** 혼선의 지배 원인은 Python import graph가 아니라 *개념적 아키텍처*(5 Axioms, G1-G22, DDD BC 패턴, pipeline stage 순서, proposal→ADR lifecycle)의 이해 부족. Graphify가 보여주는 건 `from X import Y` 관계인데, agent가 혼란스러워한 건 "왜 이 파일이 여기 있는가" / "이 결정의 근거는 무엇인가" 같은 *의도 layer*. | 높음 |
| **아키텍처 컴플라이언스 검증** | **중간.** `_boundary.py` 단일 게이트 패턴("`_boundary`만 `infrastructure` import") 위반을 시각적으로 탐지 가능. 단, 현 grep 1줄(`grep -v _boundary.py`)로 충분히 검증 가능하며, 검증 빈도는 낮다(BC 추가/변경 시). | 높음 |
| **종합 ROI** | **음수에 가까운 저양수.** 설치·설정 비용은 거의 0이나, 실질적 편익도 거의 0. 기존 정적 diagram + grep으로 Graphify가 제공하는 가시성의 90%+를 이미 확보. | 높음 |

**한 줄 종합**: Graphify는 "있으면 나쁘지 않으나, 이 프로젝트가 가진 agent 혼선 문제를 해결하지는 못한다." 진짜 gap은 *개념 구조의 자연어 내러티브 부재*지, *코드 그래프 가시성 부족*이 아니다.

---

## 1. 검증 요약 (grep 실측)

### 1.1 의존성 그래프 실태

**infrastructure → domain 방향 (단방향, `_boundary.py` 단일 게이트)**:

| infrastructure client | 사용하는 BC (`_boundary.py`) |
|---|---|
| `_common/utils.py` | **전체 7개 BC** + `_shared/*` |
| `dart/client.py` | universe, screener, catalyst, policy |
| `kis/client.py` | universe, catalyst, audit_integrity, risk_engine |
| `yahoo/client.py` | universe, catalyst, macro, audit_integrity |
| `fred/client.py` | macro |
| `llm/deepseek.py` | (domains 외 — `applications/`) |

**domain 간 의존성 (shared kernel 경유)**:

| shared module | 소비 BC |
|---|---|
| `_shared/profile_registry` | screener, universe, policy |
| `_shared/positions_store` | risk_engine |
| `_shared/audit` | screener, brief_gate (전파) |
| `_shared/brief_gate` | Stage 6 (skill) |
| `_shared/ports` | catalyst, screener, universe |
| `_shared/time` | 전체 |

✅ **컴플라이언스 확인**: `grep "from infrastructure" domains/ --include="*.py" | grep -v _boundary.py | grep -v test_` → `_shared/nav_history.py`, `_shared/time/calendar.py`, `_shared/time/clock.py`만 hit (shared kernel — 경계 내). BC domain 모듈(application/domain/*.py)은 전부 `_boundary.py`를 경유 — **위반 0건**.

### 1.2 기존 시각화 자산

| 문서 | 다이어그램 유형 | 대상 |
|---|---|---|
| `AGENTS.md` §아키텍처 | text-art flowchart | Constraint Hierarchy + Pipeline Execution Sequence |
| `pipeline-overview.md` §3 | text-art flowchart | Stage 0→6 + positions_sync→portfolio→5a~5d |
| `pipeline-overview.md` §4 | markdown table | Stage별 책임 (입력/출력/gate) |
| `proposals/parallelization-roi` | mermaid 불포함, text table | Task별 bottleneck 분석 |

Graphify가 추가할 수 있는 유일한 새 정보: **실제 Python `import` 문 기반의 자동 생성 방향 그래프**.

### 1.3 Agent 혼선 사례 (user report 대응)

사용자 보고: *"에이전트가 프로젝트 상황을 명확하게 파악 못해서 여러번 지시한 상황"*

가능한 혼선 유형과 Graphify 관련성:

| 혼선 유형 | Graphify로 해소? | 이유 |
|---|---|---|
| "어떤 BC가 어떤 infrastructure를 쓰는가" | △ 일부 | table 수준은 이미 문서화. 시각화는 직관성 +α |
| "이 파일이 왜 여기 있는가" (DDD 배치) | ✕ | import graph는 의도를 보여주지 않음 |
| "이 결정의 근거는 무엇인가" (ADR) | ✕ | 개념적 — ADR 문서를 읽어야 함 |
| "파이프라인 단계 순서 / 의존성" | ✕ | runtime data flow ≠ import graph |
| "Hard Guard G1-G22 적용 범위" | ✕ | 규칙 — import graph와 무관 |

---

## 2. 편익 분석

### 2.1 Agent 온보딩 가속

**주장**: Graphify가 import graph를 자동 시각화 → agent가 프로젝트 구조를 더 빨리 파악.

**반론**:
- 프로젝트는 7 BC + shared kernel + infrastructure의 **이미 작고 정돈된 구조**. BC 개수·의존성 edge 수(infra→BC: 최대 5, BC→BC: 0 via shared)가 작아서, graph의 정보량 < AGENTS.md의 한段落.
- Agent가 `AGENTS.md`를 읽으면 디렉토리 트리 + pipeline flowchart + stage 책임표를 한 번에 본다. Graphify는 같은 정보를 다른 표현(시각 그래프)으로 보여줄 뿐 — **신규 정보 0**.
- 오히려 혼선 유형 분석(§1.3)에서 보듯, 진짜 혼선의 80%+는 Python import graph로 답할 수 없는 질문이다.

**판정**: 기여도 낮음. agent가 `AGENTS.md` + `pipeline-overview.md`를 제대로 읽지 않으면 Graphify도 마찬가지로 무시할 가능성 높음.

### 2.2 아키텍처 컴플라이언스 검증

**주장**: `_boundary.py` 패턴 위반(domain 모듈이 infrastructure 직접 import)을 시각적으로 탐지.

**반론**:
- 현 검증은 `grep "from infrastructure" domains/ | grep -v _boundary.py | grep -v test_` 1줄로 완료. Graphify가 이보다 빠르거나 정확할 이유 없음.
- 검증 필요 빈도가 낮다: BC 추가/변경 시에만 필요. 프로젝트는 이미 BC 구조 안정기(7개 BC 모두 `_boundary.py` 보유, architecture-review-findings 잔여 2건만 cutover gate 대기).
- Graphify의 default view는 *모든* Python import edge를 보여줘서, 진짜 위반 edge가 noise에 묻힐 위험.

**판정**: 기여도 낮음. 1줄 grep이 더 정확하고 빠르다. pre-commit hook(`grep` + exit 1)만 추가하면 Graphify보다 강력.

### 2.3 문서 자동 동기화

**주장**: 코드 변경 시 Graphify가 자동 갱신 → 문서-diagram 수동 갱신 누락 방지.

**반론**:
- AGENTS.md의 pipeline flowchart는 *데이터 흐름*(Stage 0→1→...), Graphify는 *코드 import*. 둘은 직교한다 — 한쪽 갱신이 다른 쪽을 대체하지 않음.
- 실제로 `pipeline-overview.md` §3 flowchart의 "Stage 5a thesis_sync → positions/{ticker}/thesis.json" 같은 edge는 Python import graph에 **존재하지 않는다**(file I/O 기반 data flow).
- BC가 추가되면 `AGENTS.md` 디렉토리 트리 + `pipeline-overview.md` stage 표를 수동 갱신해야 하는데, Graphify는 이걸 자동화하지 않는다.

**판정**: 기여도 0. 문서 diagram의 갱신 대상(데이터 흐름, stage 순서)과 Graphify 대상(import graph)은 겹치지 않음.

---

## 3. 비용 분석

| 비용 항목 | 규모 | 비고 |
|---|---|---|
| **설치** | 0 | Zed extension marketplace 1-click |
| **설정** | 0 | Python 프로젝트 자동 인식 (별도 config 불필요) |
| **학습** | 0 | 표준 graph viz — 직관적 |
| **런타임** | 낮음 | 프로젝트 크기 200+py 미만 — graph 생성 수초 이내 |
| **유지보수** | 0 | 코드 변경 시 자동 갱신 |
| **의존성 리스크** | 없음 | editor plugin — 코드·빌드·파이프라인 무관 |

**총비용 ≈ 0**. Graphify는 순수 editor plugin — 설치·설정·유지보수 비용이 사실상 없다.

---

## 4. 대안 비교

| 대안 | 대상 문제 | 비용 | 효과 |
|---|---|---|---|
| **Graphify** | 코드 import graph 시각화 | 0 | 낮음 (정보 중복, 혼선 해소 못 함) |
| **AGENTS.md 정적 diagram 보강** | 개념 아키텍처 이해 | 낮음 (markdown 편집) | 중간 (이미 충실 — 보강 여지 적음) |
| **pre-commit `grep` boundary check** | `_boundary` 위반 탐지 | 낮음 (`.pre-commit-config.yaml` 1rule) | 높음 (자동화, CI 통합) |
| **`proposals/` → `decisions/` 승격 완료** | 결정 근거 가시성 | 중간 (ADR 작성) | 높음 (agent가 "왜"를 알게 함) |
| **BC별 README / ADR 인덱스** | domain 의도 layer 문서화 | 중간 | 높음 (agent 온보딩의 진짜 gap) |
| **Pipeline stage mermaid화** | AGENTS.md text-art를 렌더링 가능 mermaid로 | 낮음 | 중간 (시각적 개선, 단 정보량 동일) |

**우선순위 권고**: Graphify보다 **pre-commit boundary check**(비용↓ 효과↑)와 **결정 근거 문서화 보강**(agent 혼선의 진짜 원인 해소)이 우선.

---

## 5. 확신도 & 미확인

- **높음(구조)**: BC 개수(7), `_boundary.py` 패턴 존재(7/7), infrastructure клиент 분포, cross-domain import 실태 — 전부 grep 실측.
- **높음(Graphify 기능)**: Zed extension marketplace 기준 Python import graph 시각화 기능. 단, 구체적 렌더링 품질·필터링 옵션은 미실측.
- **높음(agent 혼선 원인)**: user report + 프로젝트 문서 구조 대조 기반 추정. 혼선의 지배 원인이 *개념적 아키텍처*(의도 layer)에 있음은 AGENTS.md의 복잡성(5 Axioms + G1-G22 + DDD BC + pipeline + proposals/decisions lifecycle)과 agent의 전형적 실패 모드("파일을 찾았는데 왜 여기 있는지 모름")에서 도출.
- **중간(Graphify noise 수준)**: 7 BC × 평균 10 module = 70 node + infrastructure 10 + shared 15 ≈ 95 node. edge 수는 수백 — 필터 없이 전체 graph는 noise. 단, Graphify가 BC 단위 collapse/필터링을 지원하는지 미확인.

---

## 6. 권고

1. **Graphify 도입 보류.** 비용 0이지만 편익도 0에 가깝다. "있으면 나쁘지 않다" 수준 — 다른 우선순위가 먼저다.
2. **Agent 혼선 해소의 진짜 레버**는 (a) 결정 근거 문서화 강화(proposals→decisions 승격, BC별 의도 명시), (b) AGENTS.md의 text-art flowchart를 mermaid로 교체(가독성 향상), (c) pre-commit hook으로 아키텍처 컴플라이언스 자동화.
3. **Graphify는 "재검토 예약" 정도.** 프로젝트가 3배 이상 커지거나(BC 20+), 신규 contributor가 다수 유입되는 시점에 재평가.

---

## 부록: 의존성 그래프 (정적 ASCII)

```
                    ┌──────────────┐
                    │ applications │  (run_daily_local.sh, daily_pipeline.sh)
                    └──────┬───────┘
                           │ orchestrates Stages 0→6
        ┌──────────────────┼──────────────────────────┐
        ▼                  ▼                          ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐
│  macro (E)   │  │ universe (A) │  │ catalyst (Event)     │
│  _boundary   │  │  _boundary   │  │  _boundary           │
│  ├─ fred     │  │  ├─ dart     │  │  ├─ dart             │
│  └─ yahoo    │  │  ├─ kis      │  │  ├─ kis              │
└──────────────┘  │  └─ yahoo    │  │  └─ yahoo            │
                  └──────┬───────┘  └──────────┬───────────┘
                         │                     │
                         ▼                     │
                  ┌──────────────┐             │
                  │ screener (C) │             │
                  │  _boundary   │             │
                  │  ├─ dart     │             │
                  │  └─ profile  │◄────────────┼─── _shared/profile_registry
                  └──────┬───────┘             │
                         │                     │
                         ▼                     ▼
                  ┌──────────────────────────────────┐
                  │        Stage 4 Thesis Gate        │  (skill — invest-stage4-thesis-auditor)
                  └──────────────┬───────────────────┘
                                 │
                                 ▼
                  ┌──────────────────────────────┐
                  │     risk_engine (sizing)      │
                  │     _boundary                 │
                  │     ├─ kis (read-only)        │
                  │     └─ positions_store        │◄── _shared/positions_store
                  └──────────────┬───────────────┘
                                 │
                                 ▼
                  ┌──────────────────────────────┐
                  │   Stage 6 Brief Author        │  (skill — invest-stage6-brief-author)
                  └──────────────────────────────┘

   ┌─────────────────────────────────────────────┐
   │              _shared (kernel)                │
   │  profile_registry  positions_store  audit   │
   │  brief_gate        ports             time   │
   └─────────────────────────────────────────────┘

   ┌─────────────────────────────────────────────┐
   │           infrastructure (I/O)               │
   │  dart  kis  yahoo  fred  llm  notify  krx  │
   │  _common/utils  scheduling                  │
   └─────────────────────────────────────────────┘

   ┌─────────────────────────────────────────────┐
   │           governance (policy)                │
   │  AXIOMS  decisions/  proposals/  profiles/  │
   │  capabilities/  directives/  thresholds.yaml│
   └─────────────────────────────────────────────┘

   ┌────────────┐  ┌────────────┐  ┌──────────────┐
   │ audit_     │  │  policy    │  │  telemetry/   │
   │ integrity  │  │ _boundary  │  │  operations/  │
   │ _boundary  │  │ ├─ dart    │  │  config/      │
   │ ├─ kis     │  │ └─ profile │  │  .cache/      │
   │ └─ yahoo   │  └────────────┘  └──────────────┘
   └────────────┘
```
