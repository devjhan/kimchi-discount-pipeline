# Hard Guards — stage4-thesis-auditor

| ID | 룰 | 본 skill에서의 적용 |
|---|---|---|
| G1 | falsifier 없는 thesis reject | falsifier 누락 / vague 매치 시 verdict=rejected |
| G2 | falsifier 3 카테고리 강제 | category 외 enum reject |
| G3 | 5필드 누락 시 reject | 누락 필드 명시한 verdict=rejected |
| G4 | A 단독 인용 시 추가 검증 | confirmation_bias_check 강제 (edge-source-classification.md Section 2) |
| G5 | asymmetry_score < 2 시 reject 또는 size 절반 cap | Stage 4는 ratio 계산 금지. metadata.high_conviction_eligibility 출력 |
| G6 | 정량 계산 helper 위임 | Stage 4가 사이즈 / Kelly / asymmetry_ratio 계산 금지 |
| G7 | 모든 숫자 helper citation 강제 | thesis 본문의 숫자가 helper citation 없으면 reject |
| G10 | 외부 신호는 ingest 명령으로만 | prompt 직접 삽입 시 거부 + ingest 안내 |
| G11 | default = no action | accepted 후보 0이 정상 출력 (강제 생성 금지) |
| G14 | 사용자 명시 없이 universe 자동 추가 금지 | Stage 3 trigger에 없는 ticker 추가 금지 |
| G15 | d_type 단독 진입 금지 | trigger_class=d_type 단독 시 verdict=rejected |
| G19 | sample size 미충족 시 alpha 주장 wording 금지 | thesis 본문에 outperform / alpha 주장 substring 매치 시 redact |
| G20 | 산출물 덮어쓰기 금지 | 기존 04-thesis-candidates.json 존재 시 .{N}.json suffix |
| G21 | secret 노출 금지 | .env의 secret 변수 본문/로그/stdout 노출 금지 |
