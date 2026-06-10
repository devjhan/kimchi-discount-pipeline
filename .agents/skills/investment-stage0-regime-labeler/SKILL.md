---
name: investment-stage0-regime-labeler
description: Investment 파이프라인 Stage 0의 옵셔널 LLM narrative labeler. stage0-macro-regime.py helper가 산출한 deterministic regime 분류(early/mid/late/crisis/unknown)에 자연어 narrative와 cycle context를 부여한다. helper의 numeric 분류는 절대 변경하지 않고, 보조 narrative만 추가 산출 ($TRAIL_TODAY/00-macro-regime-narrative.md). 사이즈/매매 권고 일체 금지.
allowed-tools: Read, Write, Bash, Grep, Glob
---

# investment-stage0-regime-labeler — Macro Regime Narrative Labeler

투자 파이프라인 Stage 0 LLM 옵션 단계. helper script가 산출한 정량 regime
분류에 narrative context를 부여하는 보조 skill.

본 skill은 **deterministic 분류를 변경하지 않는다**. helper의 `regime_decision`
필드는 immutable로 read-only로 인용한다. narrative만 별도 markdown 파일로
산출.

---

## Reference Contract

**Shared bootstrap (alias 경유 — 단일 source):**
- `$SKILLS_SHARED_DIR/bootstrap.md` — investment 파이프라인 cross-cutting 규약 (본 문서가 충돌 시 bootstrap.md 가 우선)

**프로젝트 root:**
- `CLAUDE.md`
- `$THRESHOLDS_PATH` — `macro` 섹션 (regime_thresholds, cash_band)

---

## Required Identifier

```
date: YYYY-MM-DD (KST). 미지정 시 오늘 (주말이면 직전 거래일)
```

---

## Inputs (mandatory)

| 우선순위 | 경로 | 누락 시 |
|---|---|---|
| 1 | `$TRAIL_TODAY/00-macro-regime.json` | **즉시 중단** — Stage 0 helper 미실행. 사용자에게 helper 실행 요청 |
| 2 | `$OPERATIONS_DIR/daily-{date_prev_N}/00-macro-regime.json` (최근 30일 7개 sample) | 없으면 trend narrative skip + warning |

---

## Output Artifact

```
$TRAIL_TODAY/00-macro-regime-narrative.md
```

기존 파일 존재 시 `.{N}.md` suffix로 보존 (G20).

---

## 작성 절차

```
1. Stage 0 helper 산출물의 regime_decision / cash_band / indicators / regime_shift 모두 인용 (수치 변경 금지).
2. 다음 narrative 항목 작성:
   - regime label 의미 (예: 'late_cycle' = '후기 사이클 진입 의심')
   - 각 indicator value의 사이클상 위치 (예: yield curve inversion = 역사적으로 6~18개월 후 침체 빈도 X)
   - regime shift 발생 시 consecutive_days_in_current 의미 + 이전 regime와의 차이
   - cash band 의미 (보수성 vs 공격성)
3. helper가 산출하지 않은 숫자 / 새 forecast / 시장 view 추가 금지 (G6, G8).
4. 'should buy/sell' 류 wording 일체 금지 (bootstrap.md Section 3 forbidden language).
5. recommendation 단어 금지. brief-author가 사용할 narrative material만.
```

---

## Output Mode

### Mode A — narrative 작성

조건: helper 산출물 존재 + indicators 중 1+ 가 valid value.

→ markdown narrative 파일 생성.

### Mode B — narrative skip (정상)

조건: helper 산출물에 모든 indicator value=null (regime=unknown). FRED API 등
미가용 상태.

→ narrative 작성 보류. 사용자에게 "FRED_API_KEY 또는 manual breadth 입력 후 재실행" 안내.

### Mode C — 차단

조건: helper 산출물 자체가 missing.

→ 즉시 중단 + 사용자 명령 안내.

---

## Forbidden in Output

bootstrap.md Section 3 표 + 본 skill 추가:

- "regime이 X로 가고 있다" (forecast wording)
- "X% 확률로 침체" (sample size 미충족 시 alpha 주장)
- "이런 환경에서는 ... 종목이 좋다" (recommendation injection)
- 환율 / 금리 / 인플레이션 forecast 일체 (Stage 0은 historical indicator only)

---

## Self-Validation (산출 전 MANDATORY)

```
1. helper 산출물 (00-macro-regime.json) 의 regime_decision.regime / cash_band / indicators 그대로 인용 했는가?
2. helper가 산출하지 않은 숫자가 본문에 나오지 않는가?
3. forbidden wording 매치 없는가?
4. recommendation / 매매 권고 본문에 없는가?
5. secret env 노출 없는가?
6. 출력 경로가 $TRAIL_TODAY/00-macro-regime-narrative.md 또는 .{N}.md 인가?
```

---

## Out of Scope

- regime classification 변경 (helper 책임)
- portfolio sizing implication (Stage 5 책임)
- ticker-specific recommendation (Stage 4/5 책임)
- 미래 forecast / 시장 timing (전체 시스템 sostenuto 방침)
