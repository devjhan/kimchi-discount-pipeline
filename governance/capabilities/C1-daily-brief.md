# C1 — 일일 go/no-go brief

## Job Story

> **When** 시장이 조용한 평범한 거래일에,
> **I want** 시스템이 자신있게 `action required = None` 을 출력하기를,
> **so I can** 침묵을 고장이 아니라 *신호* 로 신뢰하고, 불필요한 매매 충동을 억제한다.

매일 아침 1장으로 진입/청산 의사결정 근거를 얻되, **대부분의 날에 "할 것 없음" 이 정상**
출력인 brief.

## End-to-end trace

```
goal     매일 아침 사람용 markdown 1장 (30초~5분 read) 으로 entry/exit 근거 종합
trigger  launchd 07:30 KST (primary) 또는 manual invoke
stages   Stage 0~5d 산출물 전체 종합 (00-macro / 01-universe / 02-quality(-lens) /
         03-catalyst / 04-thesis / 05-sizing / 05b-falsifier / 05d-expiry)
BC       투자: Stage6 skill (investment-stage6-brief-author) — formatting only, 새 fact 0
         검증: domains/_shared/brief_gate (read-only schema validator)
config   config/user/portfolio.yaml (사이즈 섹션; 미입력 시 omit — G12)
output   operations/{date}/daily-brief.md  (+ _notify-results.json)
```

## 적용 axiom

- **#1 생존** — Default No-Action. 현금 100% 유지가 valid output.
- **#5 통계정직** — forbidden language gate + citation 의무 (모든 숫자 evidence 필수).

## 성공 / 실패 신호

- ✅ 성공: 대부분 날 "no action" + 모든 숫자에 citation + forbidden language 0.
- ❌ 실패: 매일 새 시그널 발생(노이즈 시스템) · unsourced figure · "should buy" 류 표현.

## 관련

- skill: `.claude/skills/investment-stage6-brief-author/`
- 검증 hook: `brief_citation_gate` (PostToolUse + Stop)
- forbidden language / citation 규칙: [`../specs/hard-guards.md`](../specs/hard-guards.md)
- 결정론↔LLM 경계: [ADR-0003](../decisions/0003-llm-drafts-python-commits.md)
