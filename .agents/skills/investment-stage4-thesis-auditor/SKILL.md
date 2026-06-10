---
name: investment-stage4-thesis-auditor
description: Investment 파이프라인의 Stage 4 Thesis Discipline Gate. Stage 3 catalyst trigger 종목별로 5필드 thesis (entry_catalyst / falsifier / time_horizon_months / edge_source / asymmetry_score) 작성 강제 + vague falsifier 사전 reject + edge_source 분류 (A 단독 인용 시 추가 검증) + amendment vs new entry 구분. $TRAIL_TODAY/04-thesis-candidates.json 산출. 5stone-any-specArchitect의 spec / uncertainty register 패턴을 isomorphic하게 차용하되 코드 도메인 룰 직역 금지. 정량 계산 (사이즈 / Kelly / asymmetry_ratio) 일체 금지 (Stage 5 책임). 보유 포지션 thesis 임의 수정 금지.

---

# investment-stage4-thesis-auditor — Thesis Discipline Gate

투자 파이프라인 Stage 4. Stage 3 catalyst trigger 종목에 대해 5필드 thesis를
작성/검증하고, vague / underjustified thesis는 reject한다. Default 산출은
`$TRAIL_TODAY/04-thesis-candidates.json`이며, Stage 5 sizing의 입력.

본 skill은 5stone Spec Architect (Decision Agent) 패턴을 isomorphic하게
차용한다 — `Recommended Default ≠ Decision`, `Needs Input은 묶음 질문으로
escalate`. 그러나 코드 도메인 룰 (BC, aggregate, Code-Grounded
Verification 등) 은 그대로 직역하지 않는다.

---

## Reference Contract

**Shared bootstrap (alias 경유 — 단일 source):**
- `$SKILLS_SHARED_DIR/bootstrap.md` — investment 파이프라인 cross-cutting 규약 (본 문서가 충돌 시 bootstrap.md 가 우선)

**domain/:**
- `thesis-fields-format.md` — 5필드 구조, JSON schema, verdict enum
- `falsifier-validation.md` — 3 카테고리 validation, vague pattern, anti-pattern
- `edge-source-classification.md` — A/B/C/D enum, A claim 추가 검증, anti-pattern

**프로젝트 root:**
- `CLAUDE.md` — 5 axiomatic principles
- `$THRESHOLDS_PATH` — 정량 임계값 single source (`thesis`, `enforcement`, `catalyst.trigger_rule` 섹션 필수)
- `.env` — 비-secret runtime 변수만 인용 (secret 노출 금지)

본 skill은 위 문서 중 어느 하나가 없거나 읽을 수 없으면 즉시 ERROR로 중단한다.

---

## Source of Truth Hierarchy

CONTRACT/bootstrap.md Section 1 + 본 skill 추가 항목:

1. 사용자 명시적 결정
2. CLAUDE.md
3. $AXIOMS_DIR/**/*.md
4. $SPECS_DIR/**/*.md
5. $SPECS_DIR/**/*.md
6. $THRESHOLDS_PATH
7. .env (비-secret만)
8. 본 SKILL.md
9. domain/* 본 skill 문서
10. $TRAIL_TODAY/* (Stage 0~3 산출물)
11. $POSITIONS_DIR/{ticker}/thesis.md (보유 포지션 thesis)

---

## Required Identifier

본 skill은 **date 식별자**를 입력으로 받는다 (5stone의 canonical 인자에 대응).

```
date: YYYY-MM-DD (KST). 미지정 시 오늘 (주말이면 직전 거래일로 정규화)
```

CLI 호출 예:

```
/investment-stage4-thesis-auditor                  # 오늘 날짜 기준
/investment-stage4-thesis-auditor 2026-05-04
/investment-stage4-thesis-auditor --tickers KR:003550,KR:000810
```

`--tickers` 옵션은 Stage 3 산출물의 ticker subset에 한정해 thesis 작성. 미지정
시 Stage 3에서 trigger된 모든 ticker.

---

## Artifact Discovery (필수)

본 skill은 다음 산출물을 순서대로 read. 누락 시 verdict=`needs_user_decision`
또는 즉시 중단:

| 우선순위 | 경로 | 누락 시 |
|---|---|---|
| 1 | `$TRAIL_TODAY/03-catalyst-events.json` | **즉시 중단**. Stage 3 미실행 — 사용자에게 Stage 3 cron run 요청 |
| 2 | `$TRAIL_TODAY/02-quality-filter.json` | warning + thesis 본문에 quality_check_status='unverified' marker |
| 3 | `$TRAIL_TODAY/01-universe.json` | warning (Stage 3가 정상이면 1단계 산출물은 보조 reference) |
| 4 | `$TRAIL_TODAY/00-macro-regime.json` | warning + thesis 본문에 regime_context_status='unverified' marker |
| 5 | `$POSITIONS_DIR/{ticker}/thesis.md` (per ticker) | 없으면 thesis_kind='new_entry'. 있으면 thesis_kind='amendment' |
| 6 | `$EXTERNAL_SIGNALS_DIR/{ticker}/*.md` | 있으면 본문에 referenced_external_signals 필드로 명시 (signal id만; 본문 인용 금지) |

같은 stage 산출물이 여러 개면 (`.json`, `.1.json`, `.2.json`) **mtime 최신 + suffix
높은 것** 사용. 저장 시 rule은 동일 (덮어쓰기 금지, .{N} suffix 보존).

---

## 처리 절차 (per ticker)

각 Stage 3 trigger 종목 t 에 대해 다음을 수행:

```
1. t의 catalyst event(s)를 03-catalyst-events.json에서 추출.
2. trigger_class가 a_type 또는 b_type인지 확인.
   - d_type 단독이면 즉시 verdict=rejected (G15 / $THRESHOLDS_PATH.catalyst.trigger_rule.augment_only)
3. quality_filter (Stage 2)에서 t가 통과되었는지 확인.
   - 통과 안 됨 → verdict=rejected, rejection_reason='quality filter failed'
   - 02-quality-filter.json 누락 → verdict=needs_user_decision (quality_check_status=unverified)
4. $POSITIONS_DIR/{ticker}/thesis.md 존재 여부로 thesis_kind 분류:
   - 없음 → new_entry
   - 있음 → amendment, amendment_diff에 변경 필드 명시
5. 5필드 작성:
   a. entry_catalyst — Stage 3 event id 인용
   b. falsifier — domain/falsifier-validation.md 절차로 작성 + 자가 검증
   c. time_horizon_months — $THRESHOLDS_PATH.thesis.time_horizon_months 범위 (6~60) 내
   d. edge_source — domain/edge-source-classification.md 절차로 작성 + A claim 추가 검증
   e. asymmetry_score — downside_floor / upside_ceiling 본문만 작성 (ratio 계산 금지)
6. amendment의 경우 기존 thesis와 비교:
   - falsifier 변경 → needs_user_decision (보유 포지션 thesis 임의 수정 금지)
   - edge_source 변경 → needs_user_decision
   - time_horizon_months 변경 → needs_user_decision
   - 기타 본문 보강은 amendment로 accepted 가능
7. verdict 결정:
   - 5필드 모두 valid + 기타 검증 통과 → accepted
   - hard guard 위반 → rejected (rejection_reason 명시)
   - 검증 모호 / amendment 변경 큼 → needs_user_decision (pending_user_questions 명시)
8. accepted thesis는 Stage 5로 전달 (사이즈 산출은 Stage 5 책임).
```

---

## Output Artifact

```
$TRAIL_TODAY/04-thesis-candidates.json
```

Schema는 `domain/thesis-fields-format.md` Section 3 참조. 기존 파일 존재 시
`.{N}.json` suffix로 보존 (덮어쓰기 금지).

추가 산출 (선택): accepted 후보의 thesis 본문을 `$POSITIONS_DIR/{ticker}/thesis.md`
로 **사용자 명시 명령 시에만** write. default는 candidate JSON에 본문만 보존하고,
실제 position thesis 파일 생성은 사용자가 진입 결정 후 수동 trigger.

---

## Output Mode

### Mode A — 작성 가능

다음 조건 모두 충족 시 04-thesis-candidates.json 작성:

- date 식별자 확정 가능 (input 또는 오늘 날짜로 default)
- `$TRAIL_TODAY/03-catalyst-events.json` 존재
- $THRESHOLDS_PATH의 thesis 섹션 read 가능
- accepted 후보가 1개 이상이거나, 모든 후보가 rejected / needs_user_decision로
  깨끗이 분류 가능

→ JSON 산출 후 stdout에 1줄 요약: `[stage4-thesis] date={date} accepted=N rejected=N needs_user_decision=N -> {path}`

### Mode B — 사용자 확인 필요

다음 중 하나라도 해당하면 JSON 산출 보류 + 사용자에게 묶음 질문:

- Stage 3 산출물 (03-catalyst-events.json) 누락
- Stage 2 산출물 (02-quality-filter.json) 누락 + Stage 3에 후보 1+ 존재
- 기존 보유 포지션의 amendment에서 falsifier / edge_source / time_horizon 변경 발생
- accepted 후보에 A claim이 있고 confirmation_bias_check를 본 skill이 단독으로
  답할 수 없음 (사용자 본인 industry insight 필요)
- $THRESHOLDS_PATH.thesis 섹션이 없거나 schema mismatch

질문 형식 (5stone specArchitect 묶음 질문 패턴 직역):

```
다음 항목에 대한 사용자 결정이 필요합니다:

Q1. ...
Q2. ...
...
```

질문에 답을 받기 전에는 04-thesis-candidates.json에 needs_user_decision 항목으로만 보존, accepted 분류 금지.

### Mode C — 차단

다음 hard guard 위반 시 산출 일체 보류 + 즉시 중단 + 사용자에게 hard guard
위반 사유 보고:

- 사용자가 `AGENT_BLOCK_AUTO_TRADE=false`로 변경하려는 흔적 — false면 본 skill은
  실행 거부 (G9)
- $THRESHOLDS_PATH.enforcement.numbers_evidence_required.all_numbers_in_output_must_cite_helper
  값이 false로 변경됨 — 변경 거부 (G7)
- 사용자가 본 skill에 직접 thesis prompt를 삽입 (G10 — `/ingest-external-signal`로 우회)

---

## Hard Guards (handoff doc Section 4 + bootstrap.md Section 5/7 reference)

본 skill은 다음 guard에 위배되는 산출 시도 시 즉시 중단:

| ID | 룰 | 본 skill에서의 적용 |
|---|---|---|
| G1 | falsifier 없는 thesis reject | falsifier 누락 / vague 매치 시 verdict=rejected |
| G2 | falsifier 3 카테고리 강제 | category 외 enum reject |
| G3 | 5필드 누락 시 reject | 누락 필드 명시한 verdict=rejected |
| G4 | A 단독 인용 시 추가 검증 | confirmation_bias_check 강제 (edge-source-classification.md Section 2) |
| G5 | asymmetry_score < 2 시 reject 또는 size 절반 cap | Stage 4는 ratio 계산 금지. metadata.high_conviction_eligibility 출력 |
| G6 | 정량 계산 helper 위임 | Stage 4가 사이즈 / Kelly / asymmetry_ratio 계산 금지 |
| G7 | 모든 숫자 helper citation 강제 | thesis 본문의 숫자가 helper citation 없으면 reject |
| G10 | 외부 신호는 ingest 명령으로만 | prompt 직접 삽입 시 거부 + ingest 안내 |
| G11 | default = no action | accepted 후보 0이 정상 출력 (강제 생성 금지) |
| G14 | 사용자 명시 없이 universe 자동 추가 금지 | Stage 3 trigger에 없는 ticker 추가 금지 |
| G15 | d_type 단독 진입 금지 | trigger_class=d_type 단독 시 verdict=rejected |
| G19 | sample size 미충족 시 alpha 주장 wording 금지 | thesis 본문에 outperform / alpha 주장 substring 매치 시 redact |
| G20 | 산출물 덮어쓰기 금지 | 기존 04-thesis-candidates.json 존재 시 .{N}.json suffix |
| G21 | secret 노출 금지 | .env의 secret 변수 본문/로그/stdout 노출 금지 |

---

## Self-Validation (산출 직전 MANDATORY)

본 skill은 04-thesis-candidates.json write 직전에 다음 자가 검증 모두 통과 확인:

```
1. CLAUDE.md / $THRESHOLDS_PATH / CONTRACT/bootstrap.md 읽었는가?
2. domain/thesis-fields-format.md / falsifier-validation.md / edge-source-classification.md 읽었는가?
3. Stage 3 산출물 (03-catalyst-events.json)에서만 ticker 후보 추출했는가? (Stage 4 임의 추가 금지)
4. 모든 accepted candidate가 5필드 모두 채웠는가?
5. 모든 falsifier가 vague pattern 매치되지 않는가?
6. A claim이 있는 모든 thesis가 information_edge_evidence + confirmation_bias_check 채웠는가?
7. asymmetry_score의 ratio를 본 skill이 계산하지 않았는가? (Stage 5 책임)
8. amendment의 변경 필드가 falsifier/edge_source/time_horizon인 경우 needs_user_decision으로 escalate했는가?
9. 산출물에 forbidden language (recommendation / statistical / valuation) substring 매치 없는가?
10. 산출물에 secret env 값 노출 없는가?
11. 출력 경로가 $TRAIL_TODAY/04-thesis-candidates.json (또는 .{N}.json) 인가?
12. d_type 단독 trigger ticker가 accepted로 분류되지 않았는가?
```

NO 하나라도 있으면 산출 중단 + 누락 보고.

---

## Out of Scope (본 skill이 하지 않는 것)

- 사이즈 / Kelly fraction / portfolio weight / 진입 가격 / 분할매수 plan (Stage 5 책임)
- catalyst event 자체 발견 / monitoring (Stage 3 책임)
- quality filter 통과 여부 deterministic 검사 (Stage 2 helper 책임)
- thesis 본문을 사람용 brief / Telegram push / 이메일 형식으로 변환 (Brief Author 책임)
- 보유 포지션 thesis 임의 수정 (사용자 명시 결정 후 수동 trigger)
- 외부 신호 fetch / news scraping (handoff doc G10 — `/ingest-external-signal` 별도 진입)
- 자동 매매 / 주문 / 알림 발송 (G9, G10)

---

## 호출 후 후속 권고 (자동 호출 안 함)

5stone codeBuilder의 "다른 stage skill 자동 호출 금지" 패턴 직역. 본 skill
산출 후 다음을 사용자에게 manual step으로 권고:

```
1. accepted 후보가 있다면 → Stage 5 (sizing helper) 수동 실행 권고
2. needs_user_decision 후보가 있다면 → 본 skill의 pending_user_questions 답변 후 재실행 권고
3. 모든 후보가 rejected → 사용자 액션 없음. default = no action 정상 신호 (G11)
4. amendment 후보가 있다면 → 보유 포지션 thesis 파일 변경은 사용자 결정 후 수동 trigger
```

본 skill은 Stage 5 / Brief Author / 사이즈 helper 어느 것도 자동 호출하지 않는다.
