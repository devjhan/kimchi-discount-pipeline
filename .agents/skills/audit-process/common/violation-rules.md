# Violation Rules — audit-process

## Inputs (검사 대상)

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

## AP-1 ~ AP-15 Violation Table

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
