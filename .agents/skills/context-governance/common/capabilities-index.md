# Capabilities — 파이프라인 기능 정의 (C1~C6)

> **원본**: `governance/capabilities/C1-*.md` ~ `C6-*.md` (6파일)
> **본 파일**: agent-readable 인덱스. 각 capability = Job Story → goal → trigger → stage → BC → config → output trace.

| ID | 이름 | Goal | Trigger | Stage/BC | Output |
|---|---|---|---|---|---|
| C1 | 일일 go/no-go brief | 30초~5분 read 로 entry/exit 근거 종합. 대부분 날 "할 것 없음" 이 정상 | launchd 07:30 KST 또는 manual | Stage 6 skill (`stage6-brief-author`) | `operations/{date}/daily-brief.md` |
| C2 | 보유 포지션 falsifier 모니터링 | thesis 가 falsifier trigger 에 근접 시 일일 알림. 깨진 thesis 조기 인지 | 보유 포지션 존재 | Stage 5a~5d (risk_engine 결정론) | `positions/{ticker}/drift-{date}.md` · `05b-falsifier-proximity.json` |
| C3 | 분기 LLM-가치 audit | LLM filter 가 mechanical 대비 alpha 를 더하는지 검증. 4분기 연속 열위 시 self-disable | 일별 NAV 갱신 + 분기 비교 | `audit_integrity` BC + `audit-outcome` skill | `shadow-portfolio-state.json` · `outcome-{YYYY-Q}.md` |
| C4 | 외부 신호 intake | 뉴스/트윗/블로그/리포트 → fact-only paraphrase + redaction. thesis 즉시 변경 0 | 명시적 `/ingest-external-signal` 명령 | `ingest-external-signal` skill | `telemetry/external_signals/{ticker}/{date}-{seq}.md` |
| C5 | sizing 권고 | fractional Kelly + drawdown brake 반영 사이즈 권고. context 없으면 보류 | Stage 4 thesis candidates 존재 | Stage 5 risk_engine sizing | `05-sizing-recommendation.json` |
| C6 | macro regime gate | regime 분류(early/mid/late/crisis/unknown) → cash band 결정 | 일별 시작 | Stage 0 macro BC (+ `stage0-regime-labeler` skill) | `00-macro-regime.json` (+ narrative) |

## 적용 axiom

| Capability | 주 적용 axiom |
|---|---|
| C1 daily brief | #1 생존 (Default No-Action) + #5 통계정직 (citation 의무) |
| C2 falsifier | #2 반증가능성 + #1 생존 |
| C3 LLM audit | #5 통계정직 (sample size gate) |
| C4 external signal | #3 엣지원천 (A/B/C/D 분류) + G10 |
| C5 sizing | #1 생존 (fractional Kelly + cap) + #4 비대칭 |
| C6 macro regime | #1 생존 (cash band) |
