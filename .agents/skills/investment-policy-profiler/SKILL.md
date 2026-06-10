---
name: investment-policy-profiler
description: Investment 파이프라인의 out-of-band Policy Producer 의 LLM research 단계 (Phase 6a / F-10). domains.policy 의 trigger 별 _intake (trigger + 현 profile + evidence) 를 읽어 종목별 Enrich-Cutoff profile 후보 (required_enrichments + cutoff_rules + citations + rationale_ko) 를 _profile-draft-{date}.json 으로 산출한다. **스킬은 commit 하지 않는다** — drift/version/provenance/G20 은 'python -m domains.policy.main --commit-draft <draft>' 결정론이 소유 (스킬은 환각 차단을 위해 draft 만). cutoff_rules 는 screener RuleFactory 소비 가능 문법만 (resolver whitelist 밖 metric_path 금지). 정량 계산 / 사이즈 / drift 산술 일체 금지.

---

# investment-policy-profiler — Enrich-Cutoff Profile Research (out-of-band)

`domains/policy` (Enrich-Cutoff Profile Producer BC) 의 **LLM research 단계**다. 본 BC 는
universe/screener 의 daily batch 와 **분리된 자체 일정**으로 돌며, 3-phase 다:

```
phase 1 (결정론)  python -m domains.policy.main --ticker T --trigger ...   → _intake-{date}.json
phase 2 (LLM=본 스킬)  _intake + evidence → _profile-draft-{date}.json
phase 3 (결정론)  python -m domains.policy.main --commit-draft <draft>     → ProfileRegistry 신규 버전
```

본 스킬은 **phase 2 만** 수행한다. **commit / drift / version / provenance 산술은 절대
하지 않는다** (F-10 불변식 — audit_integrity 의 "LLM→결정론 회수" 교훈 동형: LLM 은 후보만,
숫자/버전/차단판정은 결정론 코드). consumer (universe/screener) 는 `ProfileRegistry` 만
read 하며 본 스킬을 동기 호출하지 않는다.

---

## Reference Contract

본 스킬은 다음을 read 한다. 누락 시 즉시 ERROR 중단:

**Shared / 헌법:**
- `$SKILLS_SHARED_DIR/bootstrap.md` — investment 파이프라인 cross-cutting 규약 (충돌 시 우선)
- `CLAUDE.md` — 5 axiomatic principles (생존 / 반증가능성 / 엣지원천 / 비대칭 / 통계정직)
- `$SPECS_DIR/hard-guards.md` — G-rule (특히 G6/G7/G10/G20)

**입력 (phase 1 산출 + evidence):**
- `$POLICY_DRAFTS_DIR/{ticker_dir}/_intake-{date}.json` — trigger + 현 profile 동봉 (phase 1 결정론 산출)
- `$EXTERNAL_SIGNALS_DIR/{ticker_dir}/*.md` — fact-only redacted evidence (ingest-external-signal SOP 산출; raw payload 아님 — G10)

**cutoff_rules 문법 권위 (환각 차단 — 필수 참조):**
- `domains/screener/config/methods_manifest.yaml` — resolver metric_path 화이트리스트
- `domains/screener/.guidelines/01-rules.md` / `02-resolver.md` — Rule 트리 문법 (type/op/metric_path)
- `domains/_shared/profile_registry/schema.py` — `EnrichCutoffProfile` 필드 계약

> `ticker_dir` = ticker 의 `:` → `_` 치환 (예: `KR:005930` → `KR_005930`).

---

## Source of Truth Hierarchy

1. 사용자 명시적 결정
2. `CLAUDE.md` (5 철학)
3. `$AXIOMS_DIR/**/*.md`
4. `$SPECS_DIR/hard-guards.md`
5. `domains/screener/config/methods_manifest.yaml` (cutoff_rules 어휘)
6. `domains/_shared/profile_registry/schema.py` (출력 shape)
7. `_intake-{date}.json` (trigger + 현 profile)
8. `$EXTERNAL_SIGNALS_DIR/{ticker_dir}/*.md` (evidence)
9. 본 SKILL.md

---

## Required Identifier

```
ticker: KR:NNNNNN (필수)
date:   YYYY-MM-DD (KST). 미지정 시 오늘 (주말이면 직전 거래일)
```

호출 예:
```
/investment-policy-profiler KR:005930
/investment-policy-profiler KR:003550 2026-05-15
```

phase 1 (`python -m domains.policy.main --ticker KR:005930 --trigger filing:rcept_no=...`)
가 먼저 실행돼 `_intake-{date}.json` 이 존재해야 한다. 없으면 Mode B (사용자 안내).

---

## 처리 절차 (per ticker)

```
1. _intake-{date}.json read → trigger(kind/ticker/payload_ref) + current_profile 추출.
   - current_profile 이 null → new profile (v1 후보). 있으면 → amendment 후보.
2. $EXTERNAL_SIGNALS_DIR/{ticker_dir}/*.md evidence read (fact-only). signal id 만 인용,
   raw 본문을 thesis 로 직접 ingest 금지 (G10). evidence 0 = 정상 (Default No-Action 가능).
3. required_enrichments 제안: 이 종목의 thesis 검증에 필요한 enricher name set
   (예: nav_discount / spread_zscore). universe enricher registry 에 존재하는 name 만.
4. cutoff_rules 제안: screener Rule dict-tree (type=and/or/not/threshold/signal_presence/
   profile_ref). **metric_path 는 methods_manifest 화이트리스트 안에서만** (resolver 가
   소비 불가능한 path = 환각 → phase 3 가 screener 로드 시 caution 으로 격리되지만, 본
   스킬이 애초에 화이트리스트 밖 path 를 쓰지 않는 것이 1차 방어).
5. citations: 각 수치 임계의 근거 (DART 공시 / evidence signal) 를 G7 형식
   {SOURCE}@{ts}={value} 로. 임계값을 evidence 없이 지어내지 않는다.
6. rationale_ko: 왜 이 enrich+cutoff 인가 (1~3문단). "왜 시장이 틀렸나" inverse question +
   falsifier 지향. 단정/매매권고 wording 금지 (forbidden language).
7. _profile-draft-{date}.json write (아래 schema). drift/version/provenance/commit 금지.
```

---

## Output Artifact

```
$POLICY_DRAFTS_DIR/{ticker_dir}/_profile-draft-{date}.json
```

schema (= `ResearchOutput` 필드, phase 3 가 그대로 소비):
```json
{
  "ticker": "KR:005930",
  "required_enrichments": ["nav_discount"],
  "cutoff_rules": {"type": "threshold", "name": "nav_floor",
                   "metric_path": "enrichments.nav_discount.discount_pct",
                   "op": "ge", "threshold": 0.30},
  "citations": ["DART@2026-05-30T16:00:00+09:00=20260530000123"],
  "rationale_ko": "...",
  "trigger": "filing:rcept_no=..."
}
```

기존 파일 존재 시 `.{N}.json` suffix 보존 (덮어쓰기 금지 — G20).

산출 후 stdout 1줄: `[policy-profiler] ticker={ticker} date={date} enrich=N rules=M -> {path}`

---

## Output Mode

### Mode A — draft 작성
- `_intake-{date}.json` 존재 + methods_manifest / profile schema read 가능
- cutoff_rules 가 화이트리스트 metric_path + 유효 type 만 사용
→ `_profile-draft-{date}.json` 산출.

### Mode B — 사용자 확인
다음 중 하나면 draft 보류 + 묶음 질문:
- `_intake-{date}.json` 누락 (phase 1 미실행 — `python -m domains.policy.main --ticker ...` 안내)
- evidence 가 임계값을 정당화하기에 부족 (수치를 지어내야 하는 상황)
- amendment 인데 current_profile 대비 변경이 큼 (사용자 검토 필요 — 보유 정책 임의 변경 금지)
- methods_manifest 에 없는 metric_path 가 thesis 상 필요 (먼저 resolver method 추가가 선결)

### Mode C — 차단 (즉시 중단 + 사유 보고)
- 사용자가 본 스킬에 직접 profile/thesis prompt 삽입 (G10 — `/ingest-external-signal` 우회)
- 사용자가 본 스킬로 commit/drift/version 을 수행하라 요청 (F-10 위반 — `--commit-draft` 결정론 안내)
- secret env 값 노출 시도 (G21)

---

## Hard Guards

| ID | 룰 | 본 스킬 적용 |
|---|---|---|
| **F-10** | 스킬은 commit 안 함 | drift/version/provenance/registry write 절대 수행 금지 — draft 만. commit 은 `--commit-draft` 결정론 |
| **환각 차단** | cutoff_rules = RuleFactory 소비 가능 | metric_path 는 methods_manifest 화이트리스트, type 은 유효 enum 만 |
| G6 | 정량 계산 helper/결정론 위임 | drift Δ / version / Kelly / asymmetry_ratio 계산 금지 |
| G7 | 모든 수치 임계에 citation | evidence 없는 임계값 지어내기 금지 |
| G10 | 외부신호 ingest 명령으로만 | evidence 는 `$EXTERNAL_SIGNALS_DIR` (SOP redacted) 에서만; prompt 직접 삽입 거부 |
| G11 | default = no action | evidence 부족 → draft 보류가 정상 (강제 생성 금지) |
| G20 | 산출물 덮어쓰기 금지 | 기존 draft 존재 시 `.{N}.json` |
| G21 | secret 노출 금지 | `.env` secret 본문/로그/stdout 노출 금지 |

---

## Self-Validation (draft write 직전 MANDATORY)

```
1. _intake-{date}.json 의 trigger/current_profile 을 읽었는가?
2. cutoff_rules 의 모든 metric_path 가 methods_manifest 화이트리스트 안인가?
3. cutoff_rules 의 모든 type 이 유효 enum (and/or/not/threshold/signal_presence/profile_ref) 인가?
4. 모든 수치 임계에 G7 citation 이 붙었는가? (지어낸 숫자 0)
5. required_enrichments 가 universe enricher registry 에 존재하는 name 인가?
6. drift/version/provenance/commit 을 본 스킬이 계산/수행하지 *않았는가*? (F-10)
7. rationale_ko 에 forbidden language (should buy/sell, guaranteed, alpha confirmed 등) 없는가?
8. 출력 경로가 _profile-draft-{date}.json (또는 .{N}.json) 인가?
9. secret env 값 노출 없는가?
```

NO 하나라도 있으면 중단 + 누락 보고.

---

## Out of Scope (본 스킬이 하지 않는 것)

- **commit / drift 산술 / version 발급 / provenance 조립** (phase 3 `--commit-draft` 결정론)
- ProfileRegistry write (결정론 commit 만)
- universe/screener daily batch 호출 (consumer 가 registry read — 동기 호출 없음)
- trigger 발견 / DART scan (phase 1 intake 결정론 책임)
- 사이즈 / Kelly / 매매 / 알림 (G6/G9)

---

## 후속 권고 (자동 호출 안 함)

```
1. draft 가 만족스러우면 → python -m domains.policy.main --commit-draft <draft> 수동 실행 (phase 3)
2. amendment 변경이 크면 → 사용자 검토 후 commit
3. evidence 부족 → draft 보류. default = no action 정상 (G11)
```

본 스킬은 `--commit-draft` 든 어떤 결정론 단계든 **자동 호출하지 않는다**.
