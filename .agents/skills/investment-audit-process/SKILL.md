---
name: investment-audit-process
description: Investment 파이프라인 주간 process audit. 지난 7일 일별 cron run의 산출물을 모두 read해 룰 위반 (vague falsifier accepted, A 단독 claim no evidence, 사이즈 cap 위반, secret leak, forbidden language 등)을 집계. $AUDIT_DIR/process-{YYYY-WW}.md 산출. 결과 outcome (수익률)은 평가하지 않는다 (별도 outcome audit). audit-report 산출 외 어떤 stage 산출물도 수정하지 않는다.

---

# investment-audit-process — Weekly Process Audit

투자 파이프라인 주간 audit. **결과 (수익률)는 평가하지 않는다** — 룰을
지켰는지만 평가한다. process discipline이 깨지면 outcome이 좋아도 통계적
의미 없음 (statistical-honesty.md).

본 skill은 5stone-any-codeAuditor 패턴을 isomorphic하게 차용 — 결과
verdict (PASS / FAIL with severity) 산출, 다른 산출물 수정 안 함.

---

## Reference Contract

**Shared bootstrap (alias 경유 — 단일 source):**
- `$SKILLS_SHARED_DIR/bootstrap.md` — investment 파이프라인 cross-cutting 규약

**프로젝트 root:**
- `CLAUDE.md`
- `$THRESHOLDS_PATH.enforcement` + `$THRESHOLDS_PATH.statistics.outcome_audit_frequency.weekly`
- `$AXIOMS_DIR/*.md` — 5 철학 enforcement source

---

## Required Identifier

```
week: YYYY-WW (ISO week. 미지정 시 직전 ISO 주)
```

CLI:

```
/investment-audit-process                    # 직전 주 (W-1)
/investment-audit-process 2026-W18           # 명시
/investment-audit-process --range 2026-05-01:2026-05-07
```

---

## Inputs

7일 (또는 --range) 동안의 모든 일별 산출물:

| 경로 | 검사 항목 |
|---|---|
| `$TRAIL_TODAY/00-macro-regime.json` | regime classification 일관성, indicator skip 사유 빈도 |
| `$TRAIL_TODAY/01-universe.json` | universe 변동량, manual_addition 비율, exclusion 적용 |
| `$TRAIL_TODAY/02-quality-filter.json` | quality fail 비율, unknown 비율 (cache 미존재) |
| `$TRAIL_TODAY/02-quality-lens.json` | lens 평가의 evidence_status='partial' 빈도 |
| `$TRAIL_TODAY/03-catalyst-events.json` | d_type orphans 비율 (G15 위반 검사) |
| `$TRAIL_TODAY/04-thesis-candidates.json` | accepted candidate의 5필드 완전성, vague falsifier accepted 사례, A 단독 claim 사례 |
| `$TRAIL_TODAY/05-sizing-recommendation.json` | per_position cap 위반, portfolio Kelly cap 위반, drawdown brake 미적용 |
| `$TRAIL_TODAY/daily-brief.md` | forbidden language 매치, secret leak 검사, disclaimer 누락 |
| `$POSITIONS_DIR/{ticker}/drift-{date}.md` | falsifier proximity tracking 누락 (보유 포지션 vs drift 파일 1:1 mapping 검증) |

---

## Audit Rules (per-violation severity)

| ID | 위반 | severity | 검사 방법 |
|---|---|---|---|
| AP-1 | thesis 5필드 중 1+ 누락된 채 verdict=accepted | **HIGH** | 04-thesis-candidates.json scan |
| AP-2 | vague falsifier (vague_patterns_reject 매치) accepted | **HIGH** | falsifier statement substring 검사 |
| AP-3 | A 단독 claim (primary=["A"]) + information_edge_evidence null | **HIGH** | thesis edge_source field |
| AP-4 | d_type 단독 trigger ticker가 candidates에 진입 (G15) | **HIGH** | 03-catalyst-events.json d_type_orphans 비교 |
| AP-5 | per_position.max_pct 초과 사이즈 출력 | **HIGH** | 05-sizing-recommendation size_pct_of_portfolio > 0.25 |
| AP-6 | portfolio Kelly cap 초과 (sum > 0.5) without scaling | **HIGH** | 05 stats.portfolio_kelly_notes scan |
| AP-7 | drawdown -15% 도달 + brake 미적용 | **HIGH** | 05 portfolio_context.drawdown_brake_active vs sizing 비교 |
| AP-8 | 산출물에 forbidden language (recommendation / statistical / valuation) substring 매치 | **MED** | bootstrap.md Section 3 표 + $THRESHOLDS_PATH.enforcement.forbidden_language |
| AP-9 | 산출물에 secret env value substring 매치 (G21) | **CRITICAL** | env.SECRET_ENV_KEYS values vs 모든 산출물 본문 |
| AP-10 | brief의 disclaimer 누락 (USER_ACK flag false 동안) | **MED** | brief 첫 30줄 검사 |
| AP-11 | helper citation 없는 숫자 (regex로 KRW / % / 금액 substring 검사) | **LOW** | brief / candidates 본문 |
| AP-12 | 보유 포지션 vs drift 파일 1:1 mapping 누락 | **MED** | $POSITIONS_DIR/{ticker}/ vs daily drift |
| AP-13 | sample size 미충족 alpha 주장 wording | **HIGH** | $THRESHOLDS_PATH.enforcement.forbidden_language.statistical |
| AP-14 | 새 종목이 universe에 manual_addition 외 경로로 자동 추가됨 (G14) | **HIGH** | universe entries source_category 검사 + manual_additions config diff |
| AP-15 | external-signals raw payload 노출 (G22) | **CRITICAL** | external-signals 본문에 ingest 절차 marker 없는 경우 |

---

## Output Artifact

```
$AUDIT_DIR/process-{YYYY-WW}.md
```

기존 파일 존재 시 `.{N}.md` suffix 보존 (G20).

본문 구조:

```markdown
# Process Audit — Week {YYYY-WW} ({range})

## Summary

- total cron runs in week: 5 (Mon~Fri)
- total violations: N (CRITICAL: 0, HIGH: 0, MED: 2, LOW: 4)
- verdict: PASS / FAIL_HIGH / FAIL_CRITICAL

## Violations

### CRITICAL

(none)

### HIGH

(none)

### MED

- AP-8 (date 2026-05-02): brief에 "should buy" substring 매치
  - 위치: $OPERATIONS_DIR/daily-2026-05-02/daily-brief.md:42
  - 권고: brief-author skill self-validation 강화 필요

### LOW

- AP-11 (date 2026-05-03): brief에 "1억원" 숫자가 helper citation 없이 본문 등장
  - 위치: ...

## Health Indicators

- universe 일별 변동량 평균: ±3 ticker
- d_type orphans 비율: 0%
- accepted thesis 평균: 0.4건/일 (default = no action 정상)
- needs_user_decision 평균: 0.2건/일

## Recommendations

(룰 강화 / config 임계값 조정 / skill self-validation 항목 추가 등 메타 권고만.
실제 수정은 사용자 명시 결정 후.)
```

verdict enum:
- `PASS`: violation 0 또는 LOW만
- `FAIL_MED`: MED 1+ (brief 작성 / wording 수준)
- `FAIL_HIGH`: HIGH 1+ (사이즈 / falsifier / edge_source)
- `FAIL_CRITICAL`: CRITICAL 1+ (secret leak / external raw payload — 즉시 사용자 alert)

---

## Output Mode

### Mode A — audit 작성

조건: 1+ 일별 산출물 존재.

→ 본문 markdown 산출.

### Mode B — 산출물 부재

조건: 해당 주 일별 산출물 0건 (cron 미실행).

→ "no daily artifacts in week — cron 실행 확인 필요" 1줄 본문 + verdict=skipped.

---

## Hard Guards

| ID | 적용 |
|---|---|
| G6 | audit이 사이즈 / 비율 재계산 시도 금지 (산출물 read-only) |
| G7 | violation 사례에 정확한 file path + line number 인용 강제 |
| G20 | audit-report 덮어쓰기 금지 |
| G21 | secret 노출 검사 자체에서 secret 본문 audit-report에 인용 금지 (예: "AP-9: secret value=AAAA" 같은 본문 절대 금지. 위치만 명시) |

---

## Self-Validation

```
1. 일별 산출물 read-only로 처리 (수정 0)했는가?
2. AP-9 violation 본문에 secret 값 자체 인용하지 않았는가?
3. verdict가 4 enum 중 1개로 명확한가?
4. recommendations는 메타 (config / skill 강화) 수준이고, 사용자 자본 운용 권고는 없는가?
5. 출력 경로가 $AUDIT_DIR/process-{YYYY-WW}.md (또는 .{N}.md)인가?
```

---

## Out of Scope

- outcome (수익률) 평가 — `investment-audit-outcome` 책임
- 4-tier shadow portfolio state 갱신 — `domains.audit_integrity.main` 결정론 엔진 책임
- thesis / sizing 재산출 — Stage 4/5 책임
- config / skill 자동 수정 — 사용자 명시 결정 후
