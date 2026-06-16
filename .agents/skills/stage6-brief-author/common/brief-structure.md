# Brief Structure — Daily Brief Template

Stage 6 daily brief의 전체 markdown template 과 각 섹션의 conditional omit rule.

---

## Disclaimer Block

모든 brief 최상단에 고정:

```markdown
> ⚠️ DISCLAIMER:
> 본 산출물은 투자 자문이 아니며 personal research tool이다. 모든 진입/청산은
> 사용자 manual 실행이며, 결과 책임은 사용자에게 있다.
```

---

## Action Required

아래 중 1개 선택. 대부분의 날은 `None`:

- `None` — 새 후보 0, 보유 포지션 falsifier 미발동 (정상)
- `Review` — needs_user_decision 항목 N건 (Stage 4 candidate / Stage 5 sizing)
- `Alert` — falsifier 임박 (proximity high) 보유 포지션 N건 / regime shift 알람

---

## Section: Macro Context

```
regime: {label} (cash band {cash_band[0]:.0%}~{cash_band[1]:.0%})
indicators (helper citation):
  - yield_curve = {value} ({label}) — FRED@{date}
  - credit_spread = {value} ({label}) — FRED@{date}
  - vix percentile = {value} ({label}) — FRED@{date}
  - breadth = {value or 'n/a'} — manual or skip

regime_shift: {알람 여부 + consecutive days}
```

- Input source: `$TRAIL_TODAY/00-macro-regime.json` (priority 1)
- Missing fallback: 섹션 전체 omit + Pipeline Health warning
- Narrative: `00-macro-regime-narrative.md` 있으면 인용, 없으면 regime label만 간략히 작성

---

## Section: Universe Snapshot

```
total = {N} (어제 대비 {Δ})
by category: {treasury_action: M, spin_off: K, ...}
```

- Input source: `$TRAIL_TODAY/01-universe.json` (priority 3)
- Missing fallback: 섹션 omit

---

## Section: Quality + Lens

```
helper pass: {N} / fail: {N} / unknown: {N}
lens 정성 (pass 종목만): strong {N} / neutral {N} / weak {N}
```

- Input source: `$TRAIL_TODAY/02-quality-filter.json` (priority 4) + `02-quality-lens.json` (priority 5, optional)
- lens 정성 missing 시: 정성 부분 omit, helper verdict만 표시

---

## Section: Catalyst Events (Stage 3)

```
A-type primary triggers: {list ticker + catalyst type + DART rcept_no}
B-type primary triggers: {list}
D-type augmentations (단독 trigger 금지): {list}
```

- Input source: `$TRAIL_TODAY/03-catalyst-events.json` (priority 6)
- Missing fallback: 섹션 omit

---

## Section: Thesis Candidates (Stage 4)

```
accepted: {N} (사이즈 산출 가능)
rejected: {N}
needs_user_decision: {N} (사용자 답변 필요)
```

각 accepted candidate의 5필드 요약: ticker / catalyst / falsifier 본문 / horizon / edge_source / asymmetry 본문.

- Input source: `$TRAIL_TODAY/04-thesis-candidates.json` (priority 7)
- Missing fallback: 섹션 omit

---

## Section: Sizing Recommendation (Stage 5)

**전체 omit 조건**: `USER_PORTFOLIO_TOTAL_KRW` 미입력 (G12).

존재 시:

```
각 size_recommended candidate: ticker / pct / krw / rationale 마지막 1줄.
guards_applied 표시.

cash band 위반 / drawdown brake / portfolio Kelly cap 적용 사유 별도 섹션.
```

- Input source: `$TRAIL_TODAY/05-sizing-recommendation.json` (priority 8)
- Missing fallback (포트폴리오 context 입력됐으나 산출물 누락): 섹션 omit + Pipeline Health warning

---

## Section: Held Position Drift

**존재 조건**: 보유 포지션이 있는 경우만.

```
- KR:003550 LG — falsifier proximity: low
- KR:000810 삼성화재우 — falsifier proximity: medium (specific 사유)
```

- Input source: `$POSITIONS_DIR/{ticker}/drift-{date}.md` (priority 9, per held position)
- Missing fallback: 보유 포지션 0이면 섹션 생략

---

## Section: Holdings Snapshot

**존재 조건**: `positions_sync` 가 `$POSITIONS_DIR/_account/summary-{date}.json` 을 작성한 경우만.

sync_status 가 `skipped` 면 본 섹션 omit + Pipeline Health 에 1줄 보고만.

```
총자산 / 순현금 / 매수가능 현금 / 보유 종목 수 / 평가 PnL / 기간 실현 PnL —
모든 숫자에 KIS@<ts> citation. 계좌번호는 표기하지 않음 (G21 mask).

종목별 표:
| ticker | name | qty | avg | now | eval | PnL% |
|---|---|---|---|---|---|---|
```

- Input source: `$POSITIONS_DIR/_account/summary-{date}.json` (priority 11)
- positions_sync 미실행 / KIS 정책 비활성 / 계좌 미설정 시 자연스럽게 omit

---

## Section: Pipeline Health

```
- 산출 stage: 0/1/2/3/4/5 (✅ 또는 ⚠️ 또는 ❌)
- warnings 수: N
- skipped sources: {list}
```

pre-flight `validate_stage_inputs()` violation 목록이 있으면 여기에 첨부.

---

## Output Artifact

```
$DAILY_BRIEF_PATH = operations/{date}/daily-brief.md (날짜 디렉토리 루트)
```

- 기존 파일 존재 시 `.{N}.md` suffix 보존 (예: `daily-brief.1.md`)
- intermediate stage JSON (00-* ~ 05-*) 은 `$TRAIL_TODAY/` 에 산출. brief 는 부모 디렉토리에 산출.
