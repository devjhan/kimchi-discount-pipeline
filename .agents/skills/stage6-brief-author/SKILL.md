---
name: stage6-brief-author
description: Investment 파이프라인 Stage 6 — Stage 0~5 일별 산출물을 종합해 사람용 markdown brief를 합성한다. $DAILY_BRIEF_PATH 산출 (= operations/{date}/daily-brief.md). 새 fact / 숫자 추가 일체 금지 — formatting only. 외부 reference / 시장 view / 매매 권고 일체 금지. 사용자 portfolio context 미입력 시 사이즈 섹션 omit.
---

# stage6-brief-author — Daily Brief Author

Stage 0~5의 deterministic helper 산출물 + LLM lens 산출물을 합성해 사람이 읽을 markdown brief 작성. **formatting only** — 새 정보 / 숫자 / forecast / recommendation 추가 금지.

## 선행 읽기

### 공통
1. `common/brief-structure.md` — brief markdown template + 섹션별 conditional omit 규칙
2. `common/input-discovery.md` — 11-source priority table + pre-flight validator 호출
3. `common/hard-guards.md` — G6/G7/G8/G10/G11/G19/G20/G21 + forbidden language enforcement
4. `common/self-validation.md` — 7-step checklist + Out of Scope

### 분기
- `mode-write/output.md` — 1+ input 존재 시 brief 작성 조건·절차
- `mode-no-action/output.md` — 변동 0일 No Action 1줄 brief 조건
- `mode-block/output.md` — 모든 input missing 시 차단 조건·응답

## 핵심 불변식

- **Formatting only**: 새 숫자 / forecast / recommendation 일체 금지. 모든 숫자는 helper 산출물 인용
- **Conditional omit**: USER_PORTFOLIO_TOTAL_KRW 미입력 → 사이즈 섹션 omit (G12)
- **Default = No Action**: 새 후보 0, falsifier all low → "Today: No action required" 1줄이 정상

## 산출물

- `$DAILY_BRIEF_PATH` (= `operations/{date}/daily-brief.md`)

## Out of Scope

- 새 thesis 작성 (Stage 4) / 사이즈 재계산 (Stage 5) / regime 변경 (Stage 0) / universe 추가 (Stage 1) / 외부 신호 ingest / Telegram·이메일 push
