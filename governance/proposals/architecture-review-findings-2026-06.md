# Architecture Review Findings — 2026-06

`schema: investment-arch-review-v1`
`last_updated: 2026-06-05`
`status: TRANSIENT`

> **2026-06-06 — 결정 추출 완료.** 이 backlog 에 섞여 있던 *evergreen 구조 결정*(기각 기록
> 포함)은 영구 ADR 레지스터 [`governance/decisions/`](../decisions/README.md) 로 승격됐다
> (ADR-0002~0008). 그 결정 근거는 본 파일에 중복 보존하지 않으며, 본 파일은 이제 **OPEN todo
> 추적 전용**이다 (§4 삭제 규율 유지).

> ⚠️ **이 문서는 임시(transient) backlog 다 — 영구 spec 이 아니다.**
> 2026-06-02 구조 리뷰 세션에서 도출한 리팩토링 finding 중 **cutover gate 이후로 남은
> 항목**을 우선순위 / 예상 작업량과 함께 기록한 snapshot 이다. **각 finding 이 처리되면
> 해당 항목을 삭제하고, 모든 항목이 closed 되면 본 문서 전체를 삭제한다** (§4 참조).
> 거버넌스 룰(`hard-guards.md` 같은 evergreen spec)으로 승격하지 말 것 — 여기 적힌 것은
> "지킬 규약"이 아니라 "할 일".
>
> Wave 1 (cutover 무관) 항목은 처리되어 삭제됨 — 처리 내역은 코드/커밋이 기록한다.
> Wave 2 의 **F-5b**(`_shared/positions_store` 형식화 + risk_engine `_boundary` +
> thesis.json writer gap 해소)는 cutover-독립이라 **먼저 처리 완료 — 삭제됨**. 잔여
> F-2(3)·F-4(2)는 전부 **cutover gate 이후** 처리분이다.
>
> **2026-06-04 확장 — Wave 3 (F-6…F-13).** 후속 구조 리뷰에서 *아직 BC 패턴이 안
> 입혀진 flat 모듈*(risk_engine)과 *이미 리팩토링된
> BC 의 다음 단계*(macro 유연성 / policy LLM·profile) + cross-cutting(_shared/audit
> 추출 / LLM 벤더 디커플)을 추가했다. Wave 2 와 달리 **대부분 cutover 와 독립** — 현
> wave 직후 착수 가능한 다음 리팩토링 후보군이다. 동일한 §4 삭제 규율을 따른다.
>
> **2026-06-04b 확장 — Wave 4 (F-14…F-15) + 토폴로지 decision record.** storage
> 토폴로지 리뷰에서 *어느 디렉토리에 무엇이 사는가*의 오배치를 도출했다 — 재생성 불가
> 증거(nav_history)가 "재생성 가능 캐시"(cache/)에 섞임 / dead dir / dotfile 불일치.
> 아울러 "governance yaml → config/ 이전" 제안을 검토 후 **기각**(§3 decision record —
> 재제안 방지용). 전부 cutover 독립.

---

## 0. 리뷰 범위 / 한줄 요약

대상(Wave 2): `domains/screener`↔`domains/universe`, `domains/_shared/profile_registry`,
`domains/policy`, `telemetry/positions`↔`domains/risk_engine`.

대상(Wave 3, 2026-06-04): `domains/risk_engine` · `domains/macro` ·
`domains/policy`(LLM/profile) + cross-cutting(LLM-vendor 디커플).

대상(Wave 4, 2026-06-04b): storage 토폴로지 — `cache/` ↔ `telemetry/` ↔
`governance/` ↔ `config/`/`secrets/` 분류 정합.

**관통하는 결론**: 모듈 경계 *자체*는 대체로 건전하다. 잔여 finding 은 **미완
마이그레이션(cutover)** 에 몰려 있다 — F-2(3) · F-4(2) 는 policy/mechanism cutover gate
충족 이후에 처리한다. (F-5b 는 cutover-독립이라 먼저 처리 완료 — `_shared/positions_store`
형식화 + risk_engine `_boundary` + thesis.json writer gap 해소. F-2(3) 와 같은 뿌리였던
*"여러 소비자가 공유하는 contract 의 소속/형식"* 문제는 `_shared/profile_registry` 와 동형
패턴으로 해결.)

**Wave 3 결론**: 남은 flat 모듈(risk_engine)은 경계가
틀린 게 아니라 *BC 골격(_boundary · domain/application · audit · plugin registry)이 아직
안 입혀짐* — screener/universe 패턴의 롤아웃이다. 관통 주제는 *선언적·결정론 지식을
per-invocation LLM 판단에서 재현가능한 구조(domain code / 선언적 config / baseline 층 /
단일 port)로 끌어내리는 것*. whole-BC 수직 병합은 추천 0건.

**Wave 4 결론**: 경계가 아니라 *배치(어느 디렉토리)* 문제다. `cache/`(재생성 가능)에
재생성 불가 증거(nav_history)가 섞인 것 · dead dir(peer_dataset) · dotfile 불일치가
핵심 — 전부 저비용 정합. "governance yaml → config/ 이전" 제안은 시스템의 분리 축
(*소유/버전관리*: 개발자 doctrine vs 사용자 override)을 *파일 포맷* 축으로 오인 — 기각(§3).

---

## 1. 우선순위 요약 (잔여)

| ID | Finding | 우선순위 | 작업량 | 선행조건 |
|---|---|---|---|---|
| **F-2(3)** | screener↔universe legacy threshold 경로 제거 | **P3** | **L** | profile_registry cutover |
| **F-4(2)** | drift gate 차단의미 확정 (advisory → block 전환) | **P3** | **M** | PolicyEngine wiring (cutover) |

> **F-5b 처리 완료 (삭제됨).** `domains/_shared/positions_store/`(schema+serde+injected-writer
> store, `profile_registry` 동형) + `domains/risk_engine/_boundary.py`(path / KIS read-only
> G9 단일 게이트 / positions_store / `_derived` read) 신설, 3 monitor 의 중복 로더를
> `PositionsStore.load_open_raw` 로 단일화, thesis.json writer gap 을 Stage 5a `thesis_sync.py`
> (04-thesis-candidates.json → thesis.json 결정론 파생)로 해소. F-8 의 선행분이 여기서 제공됨.

작업량 범례: **S** ≤ 2h · **M** ~반일 · **L** 1일+ / multi-PR.

> **Gate 조건 (Wave 2 공통)**: `--use-profile-registry` ON default 전환 +
> `governance/policy/profiles/ticker/` 실제 profile 채움 (구 `governance/profiles/`, ADR-0013/0014로 이전) + PolicyEngine wiring(`engine=None` intake-only
> 탈출). memory `policy-mechanism-migration` 의 cutover 가 선행.

권장 순서: cutover gate 충족 후 **F-2(3) · F-4(2)**. (F-5b 는 cutover-독립 — 처리 완료.)

---

## 2. Finding 상세 (잔여)

### F-2(3) — screener↔universe: legacy threshold 경로 제거 `[P3 / L]`

**현 상태.** universe(Stage1 *enrich*)↔screener(Stage2 *cutoff*) 경계는 `01-universe.json`
단방향 핸드오프로 깨끗함. completeness gate(cutoff 의 `required_enrichments` 역참조) 명시 +
fat-contract ISP 결정은 evergreen 으로 승격됨(`governance/pipeline-overview.md` §4b +
`domains/_shared/profile_registry/schema.py` docstring).

**문제 (미완 cutover).** `--use-profile-registry` 는 OFF default(`domains/universe/main.py:184`),
`governance/profiles/` 는 `.gitkeep` 만. threshold(legacy)·profile(신규) 두 경로 병존 —
지금 느껴지는 "전략적 모호함"의 상당부분이 여기서 옴.

**권고.** profile_registry cutover 완료(`--use-profile-registry` ON default +
`governance/profiles/` 채움) 후 universe(`main.py:178-191` backward-compat 분기) · screener
의 legacy threshold 경로 제거.

**선행조건.** policy/mechanism 마이그레이션 cutover.

---

### F-4(2) — `policy`: drift gate 차단의미 확정 `[P3 / M]`

**현 상태.** commit governance(버전 발급 / drift 판정 / provenance 조립)는 빈혈
`application/commit.py` 에서 `domains/policy/domain/commit_gate.py` 로 승격됨(DDD 역전 해소,
F-4 part1). 차단/경고 의미는 `commit_gate.DRIFT_BLOCKS_COMMIT` **단일 플래그**가 결정 —
현재 advisory(False): drift 임계 초과 시 warning audit 만 기록하고 commit 진행.

**문제.** gate advisory-only. drift 초과가 commit 을 막지 않는다 — policy 가 소유한 유일한
hard 차단 수단이 비활성.

**권고.** cutover 시 `DRIFT_BLOCKS_COMMIT=True` 로 전환 — `application/commit.py` 가
이미 배선된 분기로 `ProfileDriftError` raise(hard block). 도메인 상수 한 곳 전환 +
`test_commit.py` 기대값(severity `blocking` + raise) 갱신.

**선행조건.** PolicyEngine wiring(policy/mechanism cutover).

---

## 1b. Wave 3 — 우선순위 요약 (2026-06-04 확장)

Wave 2(§1)와 달리 Wave 3 는 **대부분 cutover 와 독립**이다. screener/universe 가 받은 BC
패턴(`_boundary` · domain/application · audit · config · plugin registry)을 남은 flat
모듈에 롤아웃하는 게 골자.

| ID | Finding | 우선순위 | 작업량 | 선행조건 | 성격 |
|---|---|---|---|---|---|
| **F-11** | `policy` 2-layer profile(archetype baseline + event override) | **P3** | **L** | profile_registry cutover (F-10 완료) | — |

> **Wave 3.** F-11 은 cutover gate 뒤. (F-10 — policy LLM 을 `policy-profiler`
> 스킬로 3-phase 배선 — 은 처리 완료: f7e4cf7. §4 규율로 행/상세 삭제.)

---

## 2b. Wave 3 — Finding 상세

### F-11 — `policy`: 2-layer profile (archetype baseline + event override) `[P3 / L]`

**현 상태.** `EnrichCutoffProfile`(`schema.py`) = {required_enrichments, cutoff_rules, version,
provenance} — 섹터/아키타입/regime 필드 0. profile 은 filing 이벤트마다 ticker 별 scratch 작성.

**문제.** 시스템은 이미 non-event archetype-aware(universe `source_category`:
holding_company / preferred_share_pair / …)지만 그 인식이 profile 에 안 닿음. N holdco 가 각각
독립 작성된 cutoff_rules → 비DRY·비재현·drift noise(threshold 변화가 의도인지 LLM 분산인지
불명). `screener/config/strategies/default.yaml:6` 이 holding_company/contrarian_value 별도
strategy 를 예고하나 미구현.

**권고.** **2-layer profile**: ① archetype baseline(non-event, 선언적 governance, 거의 불변)
+ ② per-ticker event override(현 event-driven, baseline delta 만). schema 에
`archetype`/`base_profile_ref` 추가 → drift = baseline 대비 delta. F-10 스킬이 baseline 을
컨텍스트로 받아 override 만 작성. `Trigger.kind` 에 `scheduled:archetype-review`(저빈도·대부분
no-op) 추가, commit/drift 는 결정론 유지.

**범위 한정.** GICS/업종 sector 는 시스템에 전무(인프라 신설 필요) — 은행/REIT 포함 시
*metric 유효성 게이트*(은행에 ROIC cutoff 금지)로 **좁게**, screener resolver whitelist 의
섹터-조건부화로. macro regime per-ticker 주입은 **反**(cash band 와 이중계상, late_cycle 과도
긴축) — 기껏 baseline modulation 까지.

**선행조건.** profile_registry cutover (F-10 스킬 배선은 완료 — f7e4cf7).

---

## 3. Cross-cutting 메모

- **F-2(3) 의 뿌리 = (처리된) F-5b 와 동일**: 다중 소비자 공유 contract 의 소속/형식.
  `_shared/profile_registry` 가 reference 구현 — positions(F-5b)는 `_shared/positions_store`
  로 같은 틀로 **처리 완료**. F-2(3) 은 cutover 후 같은 패턴 적용 잔여.
- **F-4 = thin orchestrator 계열**: 외부 지능(PolicyEngine)을 감싸는 얇은 오케스트레이터.
  계산 무게가 큰 screener/universe 와 다른 종 — `domains/` 가 "domain-logic BC"를 뜻한다면
  경계선 멤버임을 인지.
- **Wave 3 관통 주제 = "LLM 판단 → 재현가능 구조" 회수**:
  F-10(commit 결정론 유지) · F-11(archetype baseline 선언화)이 같은 변주 — 결정론·선언적
  지식을 per-invocation LLM 에서 domain code / config / baseline 로 내린다 (audit_integrity
  엔진 회수가 그 첫 적용 — LLM 이 결정론을 침범 말 것; F-10 은 거울상으로 결정론 commit 을
  LLM 에 안 넘김). LLM 호출 단일 port 화(F-13, 처리 완료)는 그 인프라 축 — D-CORE-7 로 승격
  (구조 결정 기록: [ADR-0005](../decisions/0005-boundary-ports-and-adapters.md) · [ADR-0003](../decisions/0003-llm-drafts-python-commits.md)).
- **[추출됨 → ADR-0002 / ADR-0008]** Wave 4 의 evergreen 결정 — governance yaml → config/ 이전
  기각(소유·버전관리 축, [ADR-0002](../decisions/0002-governance-config-ownership-axis.md)),
  `.env` 명명 정규화(ADR-0002 보조 기록), storage 토폴로지 재배치(재생성가능성 축,
  [ADR-0008](../decisions/0008-storage-topology.md)) — 은 영구 ADR 레지스터로 승격됐다.
  findings §4 "승격 후 backlog 삭제" 규율에 따라 여기 중복 보존하지 않는다.

---

## Wave 5 — `_boundary` SPOF 해소 → feature-first hexagonal (F-16~F-21)

> **2026-06-05 확장.** 사용자 지적("`_boundary.py` 가 SPOF/god-module")에서 출발. 각 BC
> `_boundary` 가 path·time·citation·env·envelope·config·external-clients 5~7 무관 concern 을
> 하나의 fat 모듈로 끌어와 **ISP 위반 + 변경증폭**. application 코어는 *이미* hexagonal(주입
> 순수함수)이므로 이행 범위는 "fetch/output/citation 어댑터를 narrow Protocol port 로 추출해
> `main()` 에서 주입". 게이트는 *삭제 아님* — fat facade → **typed adapter factory** 로 진화
> (D-CORE-4 강제: `_boundary` = 유일 infra-import 파일). 선례 = F-13(LLM port)→D-CORE-7 evergreen.
> 계획 본문: `~/.claude/plans/boundary-py-spof-snuggly-penguin.md`.

| F | catch | 항목 | phase | 성격 | status |
|---|---|---|---|---|---|
| — | — | `_shared/ports/` 패턴 확립 (CitationPort/ClockPort, screener 주입 + 거버넌스 템플릿) | 0 | hexagonal(형식화) | ✅ DONE 2026-06-05 |
| F-16 | 3 | DART scan 3중복제 → `_shared/adapters/disclosure_scan` (port: `DisclosureSourcePort`). universe + catalyst 3 detector 채택; screener `detect_capital_signals_events` 는 의도적 제외(형태 상이) | 1 | hexagonal(flagship) | ✅ DONE 2026-06-05 |
| F-17 | 1,7 | KisAccountPort(G9c type-level read-only) + shadow_portfolio→init_shadow_state rename + risk_engine/AGENTS.md. **물리 concern-reorg(sizing/monitor/account) + audit/·config/ 지역화는 미채택** — domain/+application/ 레이어가 BC 골격 충족 + ViolationLog need 부재 + churn>이득 (결정기록: [ADR-0007](../decisions/0007-risk-engine-no-concern-reorg.md)) | 2 | 구조+hexagonal | ✅ DONE 2026-06-05 |
| F-18 | 2 | spx_constituents_refresh 오배치 → macro 이동 (cache 경로 무변경; risk_engine infra_common_dir dead 제거; cloud_routine_run.sh invoke 갱신) | 3 | 구조 이동 | ✅ DONE 2026-06-05 |
| F-19 | 4,7 | `domains/brief_gate` → `domains/_shared/brief_gate` 강등 (순수 validator, _boundary 없음; test→_shared/tests; hook/skill/pyproject import 갱신) + "audit" 3중 의미 disambiguate (`_shared/__init__.py` doc) | 4 | 구조 강등 | ✅ DONE 2026-06-05 |
| F-20 | 6 | AGENTS.md 결손 보강(catalyst/policy/audit_integrity AGENTS.md 신설 → 8/8). **OutputWriter/Config 전 BC 블랭킷 롤아웃은 미채택** — 측정 결과 application/domain 의 `_boundary` import 가 이미 0~1 (catalyst/universe/audit_integrity/screener=0, macro/policy=1: macro resolve_path 의도된 IO·policy commit-provenance wall-clock 으로 AsOfClock형 ClockPort 부적합). 이미 decoupled 된 BC 에 미사용 port 추가 = YAGNI (over-abstraction 경계 — macro VotingStrategy 미도입 선례 존중). 필요 seam 은 Citation/Disclosure/KisAccount/Clock port 로 이미 커버 | 5 | hexagonal | ✅ DONE 2026-06-05 |
| F-21 | 5 | EnrichCutoffProfile 휴면 cutover (= 기존 F-10→F-2(3)→F-4(2), F-11). **6a(F-10) DONE 2026-06-06**: `policy-profiler` 스킬 + `main --commit-draft`(phase 3 결정론) + `_emit_intake`(phase 1) 배선 — 3-phase, 스킬 commit 안 함. **6b~6e open (behavior, 1주 dry-run gated)**: cutover flip(universe `--use-profile-registry` ON + profiles 채움) / F-2(3) legacy 경로 제거 / F-4(2) `DRIFT_BLOCKS_COMMIT` flip — 미실행 (daily 동작 불변) | 6 | behavior(1주 dry-run) | 6a DONE / 6b~e open |

**parity 게이트(각 phase 종료조건):** pytest 회귀 0 + 경계 grep(`application/`·`domain/` 의 `_boundary` import 0; touched BC infra import 은 `_boundary.py` 만) + byte-diff(daily_pipeline `--dry-run` trails, Phase 0~5). Phase 6 은 byte-parity 대체 = **1주 dry-run diff** 후 flip(의도된 행동 변경).

**evergreen 승격 후보(패턴 정착 시):** feature-first port 패턴을 D-CORE 디렉티브로 승격(F-13→D-CORE-7 동형). 패턴 본문은 `domains/<bc>/.guidelines/05-boundaries.md` "Ports & Adapters" 절(Phase 0 신설).

---

## 4. 삭제 권고 (필수)

본 문서는 **작업 추적용 임시 snapshot** 이다. 다음 규칙으로 수명을 관리한다:

1. **항목 단위 삭제** — 각 finding 이 PR 로 처리/closed 되면 §1 표와 §2 의 해당 항목을
   **즉시 삭제**한다 (체크표시로 남기지 말 것 — 처리된 finding 은 git history 가 기록).
2. **문서 단위 삭제** — 모든 finding 이 closed 되면 (또는 본 리뷰가 stale 해지면)
   **`governance/proposals/architecture-review-findings-2026-06.md` 파일 전체를 삭제**한다.
3. **승격 금지** — 여기서 도출된 *영구 규약*이 생기면, 그 규약만 `hard-guards.md` 등
   evergreen spec 에 반영하고 본 backlog 는 삭제한다. 둘을 동시에 남기지 말 것 (SSoT 중복).
4. 6개월(≈2026-12) 경과 시까지 미처리 항목이 남으면, 여전히 유효한지 재평가 후 유지/폐기 결정.
