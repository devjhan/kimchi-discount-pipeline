# Hard Guards — stage2-quality-lens

| ID | 적용 |
|---|---|
| G6 | ROIC / debt / FCF 등 helper metric 재계산 금지 |
| G7 | 모든 정성 평가의 evidence는 helper citation 또는 DART 본문 citation 강제 |
| G8 | DART 본문 fetch 못 한 경우 `evidence_status='partial'` + lens score `'insufficient_evidence'` (hallucination 금지) |
| G13 | helper의 `fail` verdict 종목을 임의로 `pass` 처리 금지 — 본 skill은 lens 평가만, helper verdict 변경 금지 |
| G19 | "outperform" / "alpha" wording 본문 금지 |
| G20 | 산출물 덮어쓰기 금지 (`.{N}.json` suffix) |
