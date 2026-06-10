---
name: investment-stage2-quality-lens
description: Investment 파이프라인 Stage 2의 LLM 정성 lens 평가 단계. screener 패키지 (domains.screener.main)의 deterministic 통과(verdict='pass') 종목에 대해서만 4 lens (moat / 자본배분 / 회계 적신호 / 지주사 자회사 매력도)를 평가. helper의 numeric verdict는 변경하지 않고 lens 보조 의견만 추가. $TRAIL_TODAY/02-quality-lens.json 산출. ROIC/debt/FCF 등 정량 재계산 일체 금지 (helper 책임).

---

# investment-stage2-quality-lens — Quality Qualitative Lens Evaluator

투자 파이프라인 Stage 2의 hybrid LLM 단계. helper script의 deterministic
verdict가 `pass`인 종목에 대해서만 정성 lens를 평가한다. helper가 'fail'
또는 'unknown'으로 분류한 종목은 본 skill에서 평가하지 않는다.

본 skill은 정량 metric (ROIC / debt / FCF / capital_allocation 통계)을
**재계산하지 않는다**. helper가 산출한 metric을 read-only로 인용하고, 그
context에서 정성 평가만 추가.

---

## Reference Contract

**Shared bootstrap (alias 경유 — 단일 source):**
- `$SKILLS_SHARED_DIR/bootstrap.md` — investment 파이프라인 cross-cutting 규약

**프로젝트 root:**
- `CLAUDE.md`
- `$THRESHOLDS_PATH` — `quality.qualitative_lenses` 섹션 (single source)

---

## Required Identifier

```
date: YYYY-MM-DD (KST)
```

추가 옵션: `--tickers` 로 subset 평가 (default: pass verdict 전체).

---

## Inputs

| 우선순위 | 경로 | 누락 시 |
|---|---|---|
| 1 | `$TRAIL_TODAY/02-quality-filter.json` | **즉시 중단** — helper 미실행 |
| 2 | `$OPERATIONS_DIR/financials/{ticker_safe}.json` (per ticker) | 정성 평가 정확도 저하 + lens별 evidence_status='partial' marker |
| 3 | `$TRAIL_TODAY/01-universe.json` (보조) | 없으면 ticker name fallback only |
| 4 | DART 사업보고서 본문 (옵션, ticker 별 narrative source) | 없으면 회계 적신호 lens skip + warning |

본 skill은 외부 fetch 안 함 — 모든 input은 캐시된 $OPERATIONS_DIR 파일에서 read.
신규 fetch가 필요하면 사용자에게 `python -m domains.screener.main --date {date}` 실행 권고 (launchd 재활성화 시 자동 cron).

---

## 4 Qualitative Lenses (screener 패키지 quality_floor profile 의 qualitative_lenses 키)

### 1. Moat (산업 점유, 브랜드, 진입장벽)

평가 대상:
- 시장 점유율 (3년 추세)
- 브랜드 / 기술 / 네트워크 효과 / switching cost / 규모 경제
- 신규 진입자 출현 빈도

evidence 요구: helper의 financial cache + DART 사업보고서 본문 인용. 인용 없으면 score='insufficient_evidence'.

### 2. 자본배분 합리성 (소각 의지 / 재투자 ROI)

평가 대상:
- 자사주 매입 vs 소각 비율 (소각 priority)
- 배당 정책 일관성 (3~5년)
- M&A 가격 / 자회사 ROIC 변화
- 임원 보수 / 스톡옵션 dilution

evidence 요구: DART 자기주식 공시 + 배당 공시 + 분기보고서 자본 변동 표.

### 3. 회계 적신호 (영업CF vs 순이익 괴리, 충당금 패턴)

평가 대상:
- 영업CF / 순이익 ratio (3년)
- 매출채권 / 재고 회전일 변동
- 충당금 / 비영업 손익의 일회성 vs 반복성
- 감사의견 / 재고감사 history

evidence 요구: helper의 fcf_annual + revenue_recent + DART 감사보고서.

### 4. 지주사 자회사 산업 매력도 (지주사 한정)

평가 대상:
- 자회사 산업 cycle position
- 지분율 × 자회사 시총 join (helper의 NAV 캐시 활용)
- 자회사 IPO / 분할 가능성
- 지주사 discount 좁힘 catalyst presence

조건: ticker가 stage1 universe의 source_category=`holding_company` 인 경우에만 평가.

---

## Output Artifact

```
$TRAIL_TODAY/02-quality-lens.json
```

Schema:

```json
{
  "schema": "investment-stage2-quality-lens-v1",
  "generated_at": "...",
  "date": "2026-05-04",
  "stage2_helper_input": "$TRAIL_TODAY/02-quality-filter.json",
  "stats": {
    "total_evaluated": 12,
    "by_overall_lens_score": {"strong": 2, "neutral": 7, "weak": 3, "insufficient_evidence": 0}
  },
  "evaluations": [
    {
      "ticker": "KR:003550",
      "name": "LG",
      "helper_verdict": "pass",
      "lenses": {
        "moat": {
          "score": "strong",
          "rationale": "...",
          "evidence_citations": ["DART@2026-04-30={rcept_no:..., section:'사업의 내용'}"],
          "evidence_status": "complete"
        },
        "capital_allocation": { ... },
        "accounting_red_flags": { ... },
        "subsidiary_attractiveness": { ... }
      },
      "overall_lens_score": "strong",
      "lens_concerns_for_thesis": []
    }
  ],
  "warnings": []
}
```

`overall_lens_score` enum: `strong` | `neutral` | `weak` | `insufficient_evidence`.
- 4 lens 중 1+ score=`weak` 이면 overall=`weak` (보수적 가산).
- 모든 lens score=`insufficient_evidence` 이면 overall=`insufficient_evidence`.
- `weak` lens는 Stage 4 thesis-auditor 입력의 `lens_concerns_for_thesis` 배열에 reference id로 전달 — Stage 4가 thesis edge_source 평가 시 추가 검증 사용.

---

## Output Mode

### Mode A — 평가 작성

조건: helper 산출물 존재 + 1+ pass verdict ticker.

→ JSON 산출.

### Mode B — 평가 0 (정상)

조건: helper 산출물 모두 fail / unknown / caution verdict.
(`caution` = 정책상 필수 enrichment 누락 / 불량 프로파일 — `pass` 아니므로 lens 평가 대상 아님. 사람 재검토 후 다음 run 에서 재평가.)

→ stats.total_evaluated=0 의 빈 산출물 + warning. 정상 운영 신호 (G11).

### Mode C — 차단

조건: helper 산출물 missing.

→ 즉시 중단.

---

## Hard Guards

| ID | 적용 |
|---|---|
| G6 | ROIC / debt / FCF 등 helper metric 재계산 금지 |
| G7 | 모든 정성 평가의 evidence는 helper citation 또는 DART 본문 citation 강제 |
| G8 | DART 본문 fetch 못 한 경우 evidence_status='partial' + lens score 'insufficient_evidence' (hallucination 금지) |
| G13 | helper의 'fail' verdict 종목을 임의로 'pass' 처리 금지 — 본 skill은 lens 평가만, helper verdict 변경 금지 |
| G19 | "outperform" / "alpha" wording 본문 금지 |
| G20 | 산출물 덮어쓰기 금지 (.{N}.json suffix) |

---

## Self-Validation

```
1. helper 산출물에서 verdict='pass' 종목만 평가 대상으로 했는가?
2. ROIC / debt / FCF 숫자를 본 skill에서 재계산하지 않았는가?
3. 모든 정성 score에 evidence citation 또는 evidence_status marker 있는가?
4. 지주사 lens는 source_category=holding_company 종목에만 적용했는가?
5. forbidden wording 없는가?
6. helper verdict='fail' / 'unknown' / 'caution' 종목을 평가하지 않았는가? (오직 'pass' 만)
```

---

## Out of Scope

- helper의 numeric metric 재계산 또는 verdict 변경
- catalyst 평가 (Stage 3)
- thesis 작성 (Stage 4)
- 사이즈 / Kelly 계산 (Stage 5)
