---
name: investment-stage6-brief-author
description: Investment 파이프라인 Stage 6 — Stage 0~5 일별 산출물 (00-macro-regime / 01-universe / 02-quality-filter / 02-quality-lens / 03-catalyst-events / 04-thesis-candidates / 05-sizing-recommendation)을 종합해 사람용 markdown brief를 합성한다. $TRAIL_TODAY/daily-brief.md 산출. 새 fact / 숫자 추가 일체 금지 — formatting only. 외부 reference / 시장 view / 매매 권고 일체 금지. 사용자 portfolio context 미입력 시 사이즈 섹션 omit.
allowed-tools: Read, Write, Bash, Grep, Glob
---

# investment-stage6-brief-author — Daily Brief Author

투자 파이프라인 Stage 6 (post-pipeline). Stage 0~5의 deterministic helper
산출물 + LLM lens 산출물을 합성해 사람이 30초~5분 안에 읽을 수 있는
markdown brief 작성. **formatting only** — 새 정보 / 숫자 / forecast /
recommendation 추가 일체 금지.

본 skill은 Stage 0~5의 결과를 그대로 인용해 narrative만 입힌다. brief를
읽은 사용자가 진입/청산 manual 결정을 하기 위한 evidence summary 역할.

---

## Reference Contract

**Shared bootstrap (alias 경유 — 단일 source):**
- `$SKILLS_SHARED_DIR/bootstrap.md` — investment 파이프라인 cross-cutting 규약

**프로젝트 root:**
- `CLAUDE.md`
- `$THRESHOLDS_PATH` — `enforcement.forbidden_language` 필수 인용 + `default_action.most_days_no_new_candidate=true` 의 의미 적용

**Pre-flight validator (호출 강제):**
brief 본문 작성 전 `domains._shared.brief_gate.validators.validate_stage_inputs($TRAIL_TODAY)`
를 호출해 G7 envelope / citation / Stage 5 cap_violations 를 검사한다.
violations 가 있으면 본문 'Pipeline Health' 섹션에 violation list 첨부.

```bash
python3 - <<'PY'
import os, json
from pathlib import Path
from domains._shared.brief_gate.validators import validate_stage_inputs
trail = Path(os.environ["TRAIL_TODAY"])
merged, vio = validate_stage_inputs(trail)
print(json.dumps({"violations": vio, "stage_count": sum(1 for v in merged.values() if v)}, ensure_ascii=False, indent=2))
PY
```

본 skill 의 brief 작성 후 PostToolUse/Stop hook (`brief_citation_gate.sh`) 가
독립적으로 같은 validator + 본문 unsourced number 정규식 + forbidden wording
substring 검사를 수행해 violation 시 block + LLM rewrite 강제. 본 skill 은
hook 차단을 만나면 violation list 를 그대로 본문에 반영해 재시도.

---

## Required Identifier

```
date: YYYY-MM-DD (KST)
```

---

## Inputs (priority order)

| 우선순위 | 경로 | 누락 시 |
|---|---|---|
| 1 | `$TRAIL_TODAY/00-macro-regime.json` | brief의 macro 섹션 omit + warning |
| 2 | `$TRAIL_TODAY/00-macro-regime-narrative.md` (옵션) | 본문 narrative 자체 작성 (regime label만) |
| 3 | `$TRAIL_TODAY/01-universe.json` | universe 섹션 omit |
| 4 | `$TRAIL_TODAY/02-quality-filter.json` | quality 섹션 omit |
| 5 | `$TRAIL_TODAY/02-quality-lens.json` (옵션) | 정성 lens 섹션 omit |
| 6 | `$TRAIL_TODAY/03-catalyst-events.json` | catalyst 섹션 omit |
| 7 | `$TRAIL_TODAY/04-thesis-candidates.json` | thesis 섹션 omit |
| 8 | `$TRAIL_TODAY/05-sizing-recommendation.json` | 사이즈 섹션 omit (G12 사용자 portfolio context 미입력 시 자연스럽게 omit) |
| 9 | `$POSITIONS_DIR/{ticker}/drift-{date}.md` (per held position) | 보유 포지션 drift 섹션 skip |
| 10 | `$TRAIL_TODAY/event-trigger-status-{date}.json` (옵션) | event_trigger falsifier 소섹션 omit |
| 11 | `$POSITIONS_DIR/_summary-{date}.json` (옵션, positions_sync 산출) | Holdings Snapshot 섹션 omit (KIS 정책 비활성/계좌 미설정 시 자연스럽게 omit) |

input 산출물 누락은 fatal이 아님 — 가능한 섹션만으로 brief 작성. 모든 input
누락 시에만 즉시 중단.

---

## Brief Structure

```markdown
# Daily Brief — {YYYY-MM-DD} (KST)

> ⚠️ DISCLAIMER:
> 본 산출물은 투자 자문이 아니며 personal research tool이다. 모든 진입/청산은
> 사용자 manual 실행이며, 결과 책임은 사용자에게 있다.

## Action Required

(아래 중 1개. 대부분의 날은 'None')
- None — 새 후보 0, 보유 포지션 falsifier 미발동 (정상)
- Review — needs_user_decision 항목 N건 (Stage 4 candidate / Stage 5 sizing)
- Alert — falsifier 임박 (proximity high) 보유 포지션 N건 / regime shift 알람

## Macro Context

regime: {label} (cash band {cash_band[0]:.0%}~{cash_band[1]:.0%})
indicators (helper citation):
  - yield_curve = {value} ({label}) — FRED@{date}
  - credit_spread = {value} ({label}) — FRED@{date}
  - vix percentile = {value} ({label}) — FRED@{date}
  - breadth = {value or 'n/a'} — manual or skip

regime_shift: {알람 여부 + consecutive days}

## Universe Snapshot

total = {N} (어제 대비 {Δ})
by category: {treasury_action: M, spin_off: K, ...}

## Quality + Lens

helper pass: {N} / fail: {N} / unknown: {N}
lens 정성 (pass 종목만): strong {N} / neutral {N} / weak {N}

## Catalyst Events (Stage 3)

A-type primary triggers: {list ticker + catalyst type + DART rcept_no}
B-type primary triggers: {list}
D-type augmentations (단독 trigger 금지): {list}

## Thesis Candidates (Stage 4)

accepted: {N} (사이즈 산출 가능)
rejected: {N}
needs_user_decision: {N} (사용자 답변 필요)

각 accepted candidate의 5필드 요약 (ticker / catalyst / falsifier 본문 / horizon / edge_source / asymmetry 본문).

## Sizing Recommendation (Stage 5)

(USER_PORTFOLIO_TOTAL_KRW 미입력 시 본 섹션 전체 omit)

각 size_recommended candidate: ticker / pct / krw / rationale 마지막 1줄.
guards_applied 표시.

cash band 위반 / drawdown brake / portfolio Kelly cap 적용 사유 별도 섹션.

## Held Position Drift

(보유 포지션이 있는 경우만)
- KR:003550 LG — falsifier proximity: low
- KR:000810 삼성화재우 — falsifier proximity: medium (specific 사유)

## Holdings Snapshot

(positions_sync.py 가 `$POSITIONS_DIR/_summary-{date}.json` 을 작성한 경우만.
sync_status 가 'skipped' 면 본 섹션 omit + Pipeline Health 에 1줄 보고만.)

총자산 / 순현금 / 매수가능 현금 / 보유 종목 수 / 평가 PnL / 기간 실현 PnL —
모든 숫자에 KIS@<ts> citation. 계좌번호는 표기하지 않음 (G21 mask).

종목별 표:
| ticker | name | qty | avg | now | eval | PnL% |
|---|---|---|---|---|---|---|

## Pipeline Health

- 산출 stage: 0/1/2/3/4/5 (✅ 또는 ⚠️ 또는 ❌)
- warnings 수: N
- skipped sources: {list}
```

---

## Output Artifact

```
$DAILY_BRIEF_PATH                 # = operations/{date}/daily-brief.md (날짜 디렉토리 루트)
```

> 2026-05-12: brief 는 `$TRAIL_TODAY` (= `.trails/`) 가 아니라 그 부모인
> `operations/{date}/` 루트에 산출.  사용자가 디렉토리 열면 brief.md 한 파일만
> 보이고, intermediate stage JSON 은 `$TRAIL_TODAY/` (.trails/) 안에.

기존 파일 존재 시 `.{N}.md` suffix 보존.

---

## Output Mode

### Mode A — brief 작성 (가능)

조건: 1+ input 산출물 존재.

→ 가능한 섹션만으로 brief 작성, missing 섹션은 "Pipeline Health"에 reason 명시.

### Mode B — Default = No Action (정상)

대부분의 날에 모든 섹션 합쳐 다음 결과면 'None' action으로 brief 짧게:
- universe 변동 0
- catalyst events 0
- thesis candidates 0
- 보유 포지션 falsifier proximity all low

→ "Today: No action required. (정상 신호)" 1줄 + Pipeline Health 보고.

### Mode C — 차단

조건: 모든 input missing 또는 helper 산출물 schema mismatch.

→ 즉시 중단 + 사용자 명령 안내.

---

## Hard Guards

| ID | 적용 |
|---|---|
| G6 | 새 숫자 / 비율 / 사이즈 계산 일체 금지 — 모든 숫자는 helper 산출물 인용 |
| G7 | 본문의 모든 숫자에 source citation 명시 |
| G8 | helper 산출물에 없는 숫자 추측 금지 — 'n/a' 표기 |
| G10 | 외부 신호 인용 금지 — `$EXTERNAL_SIGNALS_DIR/` 산출물만 인용, raw payload 노출 금지 |
| G11 | "강한 매수" / "절대 매도" 류 wording 금지 |
| G19 | "outperform" / "alpha" wording 금지 (sample size 미충족 보장) |
| G20 | 산출물 덮어쓰기 금지 |
| G21 | secret env 노출 금지 |

bootstrap.md Section 3 forbidden_language 표 + $THRESHOLDS_PATH.enforcement.forbidden_language 두 source를 최종 redact pass에서 검사. 매치 substring은 evidence-based phrasing으로 대체 또는 redact.

---

## Self-Validation

```
1. 모든 본문 숫자가 helper 산출물 인용 (source_citation) 인가?
2. forbidden language (recommendation / statistical / valuation) substring 매치 없는가?
3. USER_PORTFOLIO_TOTAL_KRW 미입력 시 사이즈 섹션 omit했는가?
4. helper missing 섹션은 본문에 'omitted (reason: ...)' 명시했는가?
5. external-signals raw payload 노출 안 했는가?
6. secret env 노출 없는가?
7. 출력 경로가 $TRAIL_TODAY/daily-brief.md (또는 .{N}.md) 인가?
```

---

## Out of Scope

- 새 thesis 작성 (Stage 4)
- 사이즈 재계산 (Stage 5)
- regime classification 변경 (Stage 0 helper)
- universe 추가 (Stage 1 helper)
- 외부 신호 ingest (`/ingest-external-signal` 별도)
- Telegram / 이메일 push (별도 notification helper)
