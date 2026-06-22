# 배치 fetch / 배치·점진 LLM 프로파일 작성 — 효율성 개선 조사 (2026-06-06)

> **성격**: 기능 개선 후보 식별을 위한 read-only 조사 findings 문서. 코드·구현 plan 은 포함하지 않는다(본 세션 범위 밖 — 후속 작업으로 분리). 모든 핵심 주장은 `file:line` 인용이며, "✅검증"은 본 문서 작성자가 grep/read 로 독립 재확인한 것, "(보고)"는 subagent 보고서의 인용을 옮긴 것이다.
> **방법**: 3개 질문을 Opus subagent 3개로 병렬 조사 → 각 보고서 `/Users/jhan_acc/Documents/tmp/Q{1,2,3}-*.md` (부록 참조). 본 문서는 그 종합 + 핵심 주장 독립 검증.
> **중요 맥락**: 파이프라인은 현재 **미활성**(`schedules.yaml:39` `daily_pipeline.enabled:false`, `.cache/`·`telemetry/`·`operations/` 비어 있음). 따라서 모든 *부하/빈도* 주장은 **설계 의도 기반 추정이며 실측이 아니다**. 착수형 권고는 전부 "1주 운용 로그 측정 선행" 조건부.

---

## 0. 요약

| # | 질문 | 답 | 확신도 | 실 actionable? |
|---|---|---|---|---|
| Q1 | 기존 daily pipeline 은 enrich-cutoff 프로필을 **새로 작성**하는가? | **아니오.** daily 는 프로필을 **read-only 소비만** 한다. 작성은 별도 BC(`domains/policy`) + 별도 schedule 의 **out-of-band 3-phase**이며, 현재 cutover 미완으로 프로필 store 가 비어 있어 산출 영향 0. | 매우 높음 | — (현 설계가 의도대로 동작) |
| Q2 | 배치 단위 raw-data fetch 파이프라인이 더 효율적인가? | **"bulk fetch stage" 형태는 불필요하나, fetch 효율 자체는 실live한 과제 (초판 정정).** universe 는 ~13 이 아니라 **시장 전체 unbounded(수백~1000+ 티커 추정)** 이고 screener 가 그 전 entry 에 per-ticker DART 재무 fetch 를 건다. 그래도 외부 API 에 multi-ticker bulk endpoint 가 없어 "batch stage" 는 호출 수를 못 줄인다. 진짜 레버는 ① **universe upstream 협소화**(activist source 가 모든 5% 공시를 admit — 과대 net), ② per-ticker fetch **병렬화**(rate-limit 게이트), ③ DART 공시 스캔 중복 제거. | 중간(scale 추정은 미측정) | **△ 3건** (측정/설계검토 선행) |
| Q3 | 배치/점진적 LLM 프로파일 작성이 더 효율적인가? | **둘 다 불필요.** 현 방식 = 1 ticker × 1 trigger × whole-profile one-shot. (A)배치 프롬프트는 trigger 희소+context 오염으로 음 ROI, (B)점진 부분-필드는 schema(분리불가)·whole-version commit·drift 자기충돌과 정면 충돌. **진짜 gap 은 cold-start 부트스트랩 메커니즘 부재**이며, 이는 배치/점진이 아니라 "단건 N회 순차 오케스트레이션 러너"로 푸는 것이 거버넌스 정합. | 높음 | **△ cold-start 러너** (cutover 선결조건) |

**한 줄 종합**: Q1·Q3 은 "현 out-of-band 분리 + trigger-driven one-shot 이 거버넌스와 정합 → 배치/점진 불필요"로 명확하다. Q2 는 **초판의 'universe ~13' 이 오류**여서(아래 §3 정정) 재평가가 필요하다 — universe 는 시장 전체 unbounded 라 fetch 부하가 작지 않다. 다만 사용자 질문의 *문자 그대로의* "bulk fetch 파이프라인"은 외부 API 에 bulk endpoint 가 없어 호출 수를 못 줄이므로 그 형태로는 여전히 부적합하고, 실효 레버는 "batch"가 아니라 **upstream universe 협소화 + per-ticker fetch 병렬화 + 공시 스캔 dedup**이다.

---

## 1. 검증 요약 (작성자 독립 재확인)

subagent 결론을 그대로 옮기지 않고, 결론을 좌우하는 토대 주장을 직접 grep/read 로 재확인했다:

- ✅ `applications/` 전체에 `domains.policy` 호출 **0건** (grep) — daily 가 policy 를 부르지 않음.
- ✅ profile registry `.commit()` 의 유일한 non-test caller = `domains/policy/application/commit.py:93` (risk_engine 의 `positions_store().commit` 은 thesis store 로 별개).
- ✅ `governance/profiles/` = `.gitkeep` 만, `telemetry/policy_drafts/` 빈 디렉토리.
- ✅ `schedules.yaml:82-92` `policy_producer` = 별도 **주간** schedule, `enabled:false`; `:39` `daily_pipeline` 도 `enabled:false`.
- ✅ `iter_disclosures` 가 universe(`dart_disclosure_filter.py:132`) + catalyst 5개 호출처에서 각각 `_boundary` 경유로 **중간 캐시 계층 없이** 직접 호출됨 — 시장 전체 스캔 중복의 구조적 근거.
- ✅ `daily_pipeline.sh:161-179` `run_stage` = stage 마다 `"$PYTHON_BIN" -m "$module_path"` **별도 프로세스** → stage 간 in-process 공유 불가.
- ✅ KIS 가격 = `FID_INPUT_ISCD` 단건(`kis/client.py:322,368`), DART 재무 = 단일 `corp_code`(`dart/client.py:201-234`), `iter_disclosures` corp_code 미지정 시 시장 전체(`:116-145`) — **bulk endpoint 부재** 확정.
- ✅ resolver whitelist = enrichment 3 (`resolver.py:23-25`) + `_REGISTRY` 6 (`:111,119,127,135,143,149`) = **정확히 9개**.
- ✅ `profile_registry/schema.py:8-13` "프로파일은 **단일 정책 단위 — 쪼개지 않는다**(ISP F-2)" + `EnrichCutoffProfile` frozen(`:49-93`, 필드 patch API 없음).

### ⚠️ 초판 정정 — universe 규모 ("~13" 은 오류)

후속 검증에서 Q2 subagent 의 "universe ~13 종목" 이 **잘못된 framing** 임을 확인했다. "~13" 은 *가격 enricher*(nav_discount/spread_zscore) 대상(지주사 자회사 + 우선주 페어)만 센 것이고, **screener 가 DART 재무를 fetch 하는 실제 universe 는 시장 전체에서 unbounded 로 유입된다**:

- ✅ `universe/config/sources.yaml:36-77` 의 `dart_disclosure_filter` 3 source(treasury_action / spin_off_or_merger / activist_filing)는 **시장 전체 DART 공시**를 키워드 매칭으로 스캔.
- ✅ `dart_disclosure_filter.py:118-180` `discover()` 는 매칭 건마다 `entries.append(self._build_entry(md))` — seed 리스트 무관.
- ✅ universe source 는 `scan_disclosures` 에 `keep` 필터를 **전달하지 않음**(`disclosure_scan.py:44-45,80-82` — `keep` 은 catalyst 전용). activist 키워드는 `"주식등의대량보유상황"` 하나뿐이라 **시장의 모든 5% 대량보유 보고서**가 admit 됨. `annotate_filers`(강성부/라이프/안다)는 `known_activist` 플래그만 달 뿐 **필터 아님**(`:200-211`).
- ✅ 크기 cap 없음: `exclusions.yaml` = `tickers: []`, `build_universe.py:127-135` dedup 키는 `(ticker, source_category, source_citation)` (ticker 단일 dedup 도 아님).
- ✅ `screen.py:76-96` 는 **전 universe entry** 에 cache miss 시 무조건 per-ticker DART 재무 fetch — quality pre-filter gate 없음.
- **추정(미측정)**: 한국 시장 5% 대량보유 보고는 연간 수천 건, 고유 티커로도 **수백~1000+** 규모. 자사주취득/소각·분할/합병 추가. → 실제 universe 는 **수백 종목 규모로 추정**(파이프라인 미활성 → live 실측 불가, 도메인 추론).

**영향**: Q2 의 "scale 이 작아 배치 불필요" 논거는 무효. fetch 부하는 실제로 크다. 단 "bulk endpoint 부재 → batch stage 가 호출 수를 못 줄임"(✅)은 불변이라, 결론의 *형태*는 바뀌어도(§3 재작성) 사용자가 말한 "bulk fetch 파이프라인" 자체의 부적합 판정은 유지된다.

Q1·Q3 의 결론·확신도는 재확인과 일치(이견 없음). **Q2 만 위와 같이 정정**한다.

---

## 2. Q1 — daily pipeline 은 enrich-cutoff 프로필을 작성하지 않는다

### 결론
**No.** daily pipeline(`daily_pipeline.sh` / `run_daily_local.sh`)은 프로필을 **생성·갱신하지 않으며**, universe/screener 가 **read-only 로 소비**만 한다. 프로필을 write 하는 유일 코드 경로(`ProfileRegistry.commit` ← `commit_profile` ← `domains.policy.main`)는 daily 스크립트가 호출하지 않는다.

### 근거 (검증됨)
- daily orchestrator stage 목록(`daily_pipeline.sh:201-236`): positions_sync / portfolio_state_derive / macro / universe / screener / catalyst / risk_engine 5종 — **`domains.policy.*` 없음** ✅.
- 프로필 writer 유일 경로: `registry.commit`(`profile_registry/registry.py`) ← `commit_profile`(`policy/application/commit.py:93`) ← `policy/main.py`(phase 3 `--commit-draft`). daily 는 이 진입점 미호출 ✅.
- daily 의 프로필 사용은 read 전용: universe `--use-profile-registry`(기본 **OFF** = backward-compat applies_to), screener `rule_for` closure(`load_latest` read → 없으면 `default_rule` fallback) (보고, Q1 §C).

### 프로파일 lifecycle (out-of-band)
```
[trigger] ─► phase1 결정론  policy.main --ticker --trigger  → _intake-{date}.json
                              (별도 schedule: policy_producer, 주간, enabled:false)
          ─► phase2 LLM      /policy-profiler                  → _profile-draft.json  (commit 안 함, F-10)
          ─► phase3 결정론   policy.main --commit-draft       → governance/policy/profiles/ticker/{tk}/vN.yaml  (유일 writer)
                                                                        │ load_latest (READ ONLY)
   daily cron ──────────────────────────────────────────────────────────┤
     Stage1 universe (--use-profile-registry, 기본 OFF) ◄────────────────┤
     Stage2 screener (rule_for closure) ◄─────────────────────────────────┘
```
writer 3-phase 전부 **daily cron 바깥**(별도 주간 schedule + 수동 phase 3). daily 는 reader 2개만 포함.

### 의도된 설계 근거
ADR-0003("LLM drafts, Python commits"), F-10/F-21, `domains/policy/AGENTS.md`("daily_pipeline 과 **분리된 자체 일정**, consumer 는 registry 만 read — policy 동기 호출 안 함"). LLM 스킬에 commit 권한을 주지 않아 환각이 영구 store 에 침투하는 것을 차단(5철학 #5 통계적 정직성, #1 생존)(보고, Q1 §F).

### 현 상태
cutover 미완 3종 미flip: ① `governance/profiles/` 비어 있음, ② universe `--use-profile-registry` OFF, ③ `DRIFT_BLOCKS_COMMIT=False`. 따라서 **프로필이 산출에 미치는 영향 = 0** (현재 backward-compat 경로만 동작). (보고+✅)

---

## 3. Q2 — 배치 raw-data fetch (초판 정정판)

> 초판은 "universe ~13 → scale 작음 → 배치 불필요"로 결론했으나 **universe 규모 산정이 틀렸다**(§1 ⚠️ 정정). 본 절은 그 정정을 반영한 재평가다.

### 결론 (수정)
사용자가 말한 *문자 그대로의* "multi-ticker bulk fetch 파이프라인" 은 **여전히 부적합** — 외부 API 에 bulk endpoint 가 없어 호출 *수*를 못 줄이기 때문이다(아래 #1). 그러나 **fetch 효율 자체는 실재하는 과제**다: universe 가 시장 전체 unbounded(수백~1000+ 추정)라 screener 의 per-ticker DART 재무 fetch 부하가 작지 않다. 실효 레버는 "한데 모아 받기(batch)"가 아니라 **(A) universe upstream 협소화, (B) per-ticker fetch 병렬화, (C) 공시 스캔 dedup** 세 가지다.

### #1. "bulk fetch stage" 가 호출 수를 못 줄이는 이유 (불변, ✅)
KIS 가격(`FID_INPUT_ISCD` 단건), DART 재무(단일 `corp_code`, `fetch_financial_statements`) 모두 per-ticker 단건 endpoint. 외부 API 가 multi-ticker bulk 를 미지원하므로, "배치 prefetch stage" 로 모아도 **내부적으로 N번 단건 호출은 동일** → API 호출 수 절감 0. 이 사실은 universe 가 13이든 1000이든 불변이다. → **"한 번에 다 받는 파이프라인"이라는 형태 자체는 효율 이득이 없다.**

### #2. 그러나 fetch 부하는 작지 않다 (정정의 핵심)
- screener(`screen.py:76-96`)는 **전 universe entry** 에 cache miss 시 무조건 per-ticker DART 재무 fetch. quality pre-filter gate 없음.
- universe 는 `dart_disclosure_filter` 3 source 가 시장 전체를 키워드 스캔해 매칭 티커를 **무제한** 유입(`sources.yaml:36-77`, `dart_disclosure_filter.py:118-180`). 특히 activist source 는 `keep` 필터 없이 **모든 5% 대량보유 보고서**를 admit. cap 없음(exclusions 빈 리스트).
- → 실제 fetch 대상 universe = **수백 종목 규모로 추정**(미측정). cold-start(빈 캐시) 시 수백 건 sequential DART 재무 fetch = 실질 wall-clock + DART rate-limit 노출. 30일 캐시가 이 부하를 흡수하지만, 그만큼 **캐시가 핵심**이고 cold-run 비용은 크다.

### #3. 실효 레버 3종 (배치 아님)

**(A) universe upstream 협소화 — 가장 큰 레버 (설계 검토 후보)**
activist source 가 시장의 *모든* 5% 대량보유 보고를 admit 하는 것이 의도인지 검토 필요. 대다수는 특수상황과 무관하고 screener quality filter 에서 탈락하는데, **탈락할 종목의 재무까지 전부 fetch** 한다. `annotate_filers` 를 *필터*로 승격하거나(known funds 만 keep) 추가 gating 을 두면 fetch 대상이 수백 → 수십으로 떨어진다. 어떤 fetch 최적화보다 효과가 크다. *(단 universe recall 을 의도적으로 넓게 둔 설계일 수 있어 — 5철학상 "사냥터 A"를 좁히는 결정이라 사용자 판단 필요.)*

**(B) per-ticker DART 재무 fetch 병렬화**
수백 건 sequential 호출의 wall-clock 을 rate-limit 안에서 동시성(예: 소규모 worker pool)으로 단축. 초판이 "scale 13" 가정으로 기각했으나, 실제 scale 에선 유효. 단 DART rate-limit/secret 안전이 제약이고 BC 경계 안(screener `_boundary`)에 머물러야 함.

**(C) DART 공시 스캔 중복 제거 (초판의 유일 발견 — scale 반영 시 가치 상향)**
`iter_disclosures` 는 캐시되지 않으며(✅ 전 호출처 live), 같은 run 에서 시장 전체 공시 list 를 두 stage 가 독립 스캔한다:

| pblntf_ty | Stage 1 (universe) | Stage 3 (catalyst) | 겹침 |
|---|---|---|---|
| `B` 주요사항 | `treasury_action` 12mo + `spin_off_or_merger` 24mo | `treasury_cancellation` 30d + `spin_off_merger` 60d | 동일 endpoint·유사 키워드 |
| `D` 지분공시 | `activist_filing` 12mo | `activist_5pct` 30d | 동일 endpoint·동일 키워드 |

- "per-ticker N배"가 아니라 "stage 2벌 + lookback 차이" 문제 → 통합이 아니라 *공유*. 12~24mo 시장 전체 스캔은 페이지가 많아(미측정) scale 가 커질수록 이득↑.
- **형태(개념만)**: `disclosure_scan.py:36`(universe·catalyst 공유 진입점)의 `DisclosureSourcePort` 주입 지점에 run-scoped 공유 캐시 어댑터 — BC 경계·port 무손상. 단 `run_stage` 가 stage 별 별도 프로세스(✅)라 in-process 불가 → 짧은 TTL(수 시간) 디스크 캐시.

### 선결 조건
세 레버 모두 **실측 선행**: 파이프라인 미활성으로 `.cache/`·로그가 비어 universe 실제 크기·DART 페이지 수·rate-limit 빈도가 미측정. 1주 운용 로그로 (a) universe 실 종목 수, (b) DART 재무/공시 호출 수·실패율을 측정한 뒤 우선순위 확정. 특히 (A)는 효율이 아니라 **전략(사냥터 폭)** 결정이라 사용자 판단 필수.

### 별개 트랙
Stage 0a SPX breadth 가 ~500 종목 Yahoo per-ticker 루프(캐시 없음, `breadth_fetch.py:74-84`). 한국 universe 와 무관하나 절대 호출 수는 큼 → **breadth 결과를 1일 TTL 캐시**하는 게 독립 개선책.

---

## 4. Q3 — 배치/점진 LLM 프로파일 작성: 둘 다 불필요, 실체는 cold-start

### 현 작성 방식 (검증됨)
`policy-profiler` 스킬 1회 invoke = **1 ticker × 1 trigger × whole-profile one-shot**. 세 축 모두 단건(`SKILL.md:62-97`, `policy/main.py:145,176-185`, `domain/research_result.py:8-22` frozen 4필드). 전종목 DART 일괄 스캔은 **미배선**(`policy/_boundary.py:99-101` 정의는 있으나 `main.py` 호출 0).

### 거버넌스 제약 (배치·점진을 봉쇄)
- **분리 불가 단일 단위** ✅ — `profile_registry/schema.py:8-13`(ISP F-2): "universe-view/screener-view 로 쪼개지 않는다." 필드 patch/merge API 부재 → "일부 필드만" 표현 불가.
- **매 commit = whole new `vN.yaml`** — `registry.commit` 항상 신규 파일(G20), `next_version=prev+1`. 부분 갱신 = patch 아니라 새 전체 버전 (보고, Q3 §2).
- **drift 자기충돌** — placeholder→실값 교체가 `drift.py:43-48` `max_threshold_delta` 로 잡혀, cutover 후 `DRIFT_BLOCKS_COMMIT=True` 면 2회차부터 차단. drift 는 "의도 변경 vs LLM 분산" 구별 불가(ADR-0003) (보고, Q3 §3).
- **whitelist ~9** ✅ — cutoff_rules metric_path 가 9개로 협소 → 종목당 프로파일이 작은 rule-tree 라 배치로 절감할 토큰도, 분할할 1회 부하도 미미.
- **F-10** — 스킬은 commit 안 함. 배치해도 phase 3 commit 은 종목별 단건 N회 그대로 → 결정론 절반은 절감 0.

### 평가
- **해석 A (1 invoke = N tickers, 진짜 배치 프롬프트)**: 정상 운영 **불필요**(trigger 희소 + context dilution/G7 citation 교차오염 + commit 반복 미절감). cold-start 만 **조건부** — 단 "배치 프롬프트"가 아니라 후술 오케스트레이션 러너로.
- **해석 B (점진 부분-필드)**: **불필요**(분리불가 schema·whole-version·drift 셋 다 충돌 + 미완 프로파일이 screener 를 *의미적으로* 오통과시킬 위험 — 안전망은 구조 손상만 caution 격리).

### 진짜 gap = cold-start 부트스트랩 메커니즘 부재 (actionable 후보 #2)
`governance/profiles/` 가 빈 상태(✅)인데 cutover gate 는 "profiles 채움"을 선결조건으로 요구하면서 **채우는 메커니즘은 미정의**(`architecture-review-findings-2026-06.md:84-86`). 비효율의 실체는 LLM "작성 방식"이 아니라 **0→N 종목을 채우는 운영 반복**이다.
- **정합 해법(개념만)**: 종목 리스트를 받아 종목마다 `[phase1 intake → 스킬 1회 invoke(여전히 1 ticker) → 사람 리뷰 → phase3 commit]` 를 **순차 구동**하는 얇은 부트스트랩 러너. 바뀌는 건 사람의 세션 왕복 → 1 러너 호출뿐. F-10/G20/G7/drift 전부 무손상(cold-start 는 prev=None → drift 0, `drift.py:37`).
- "해석 A 배치 프롬프트"가 아니라 **정상 단건을 N회 순차 실행** — context 오염 0.

---

## 5. 교차 결론 & 개선 후보 우선순위

공통 결론: 사용자 질문의 *문자 그대로의* "한 번에 다 받는 batch/bulk 파이프라인" 형태는 (Q2) bulk endpoint 부재로 호출 수 이득이 없고 (Q3) trigger-driven 거버넌스와 충돌해 부적합하다. 그러나 **Q2 정정 결과 fetch 효율은 실재 과제**이며, 실효 레버는 "batch"가 아닌 가벼운 형태다:

| 우선순위 | 후보 | 형태 | 선결조건 | 근거 |
|---|---|---|---|---|
| 1 | **universe upstream 협소화** | activist source 의 5% 공시 admit 범위 gating (효율 아닌 전략 결정) | **사용자 판단**(사냥터 폭) + universe 실 크기 실측 | Q2 §3(A) |
| 2 | per-ticker DART 재무 fetch 병렬화 | screener `_boundary` 안 동시성 worker (rate-limit 게이트) | DART 호출 수·rate-limit 실측 | Q2 §3(B) |
| 3 | DART 공시 스캔 중복 제거 | run-scoped 공유 캐시(디스크 짧은 TTL), `disclosure_scan.py` 주입 지점 | DART 페이지 수 실측 | Q2 §3(C) |
| 4 | cold-start 프로파일 부트스트랩 | 단건 N회 순차 오케스트레이션 러너(배치 아님) | cutover(6b–6e) 진행 결정 | Q3 §진짜 gap |
| (별개) | SPX breadth 500-루프 | breadth.yaml 1일 TTL 캐시 | — | Q2 §별개 트랙 |

> 본 세션은 "코드·계획 작성 X" 범위이므로 위는 **후속 작업으로 분리**해 다룬다. 후보 1 은 효율이 아니라 universe recall 폭(5철학 "사냥터 A")에 관한 전략 결정이라 코드보다 사용자 의사결정이 먼저다. 나머지는 1주 운용 로그 실측 후 우선순위 확정.
>
> **ROI 후속 조사(2026-06-06)** — [parallelization-roi-2026-06.md](parallelization-roi-2026-06.md): 후보 2(per-ticker fetch 병렬화)는 **후순위 강등**(source 천장 KIS 20/sec·DART throttle + client thread-unsafe 안전화 비용 > cold-start 1회 절감, 측정 후 조건부), 후보 4(cold-start 부트스트랩)는 **순차 러너로 확정**(profile 스킬 병렬화 비채택 — 지배 bottleneck인 인간 검토·evidence 부재를 병렬이 못 줄임). 후보 1(universe 협소화)이 두 Task 공통 상위 레버로 재확인.

---

## 6. 확신도 & 미확인

- **확신도 높음(구조)**: Q1 Yes/No, Q2 bulk endpoint 부재·공시 스캔 중복·**universe unbounded 구조**, Q3 작성 단위·거버넌스 제약 — 모두 코드 직접 인용으로 grounded(✅ 재확인).
- **확신도 중간(scale)**: Q2 의 universe 실 종목 수("수백~1000+")는 시장 구조(모든 5% 공시 admit) + 도메인 추론이며 **live 미측정**. "~13"이 틀린 것은 확실하나 정확한 수는 운용 로그 필요. 초판이 이 수를 잘못 잡아 결론을 오도했음(정정 완료).
- **미확인(공통, 가장 중요)**: 파이프라인 미활성으로 `telemetry/`·`.cache/`·`operations/` 가 비어 **실측 부하/trigger 빈도 데이터가 없다**. Q2 의 fetch 부하·Q3 의 "trigger 희소"는 설계 의도 기반 추정이다. → 후보 착수 전 1주 운용 로그 필수.
- **미확인(부수)**: DART 시장 스캔 실제 페이지 수, 실 운용 rate-limit/503 빈도, `policy/ports/llm.py` PolicyEngine 구현체 wiring 여부, cutover 후 `DRIFT_BLOCKS_COMMIT=True` 에서 실제 차단 빈도. 어느 것도 위 결론을 뒤집지 않음.

---

## 부록: subagent 원본 보고서

- Q1: `/Users/jhan_acc/Documents/tmp/Q1-daily-pipeline-vs-enrich-cutoff-profiles.md`
- Q2: `/Users/jhan_acc/Documents/tmp/Q2-batch-raw-data-fetch-efficiency.md`
- Q3: `/Users/jhan_acc/Documents/tmp/Q3-batch-incremental-llm-profile-authoring.md`
