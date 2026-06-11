# Hard Guards — Stage 6 Brief Author

Stage 6 brief 작성 시 적용되는 AGENTS.md Hard Guards 및 enforcement 규칙.

---

## Applicable Hard Guards

| ID | 적용 |
|---|---|
| G6 | 새 숫자 / 비율 / 사이즈 계산 일체 금지 — 모든 숫자는 helper 산출물 인용 |
| G7 | 본문의 모든 숫자에 source citation 명시 (`{source}@{ISO_timestamp}={value}` 형식) |
| G8 | helper 산출물에 없는 숫자 추측 금지 — 'n/a' 표기 |
| G10 | 외부 신호 인용 금지 — `$EXTERNAL_SIGNALS_DIR/` 산출물만 인용, raw payload 노출 금지 |
| G11 | "강한 매수" / "절대 매도" 류 wording 금지. Default = No Action 원칙 |
| G19 | "outperform" / "alpha" wording 금지 (sample size 미충족 보장) |
| G20 | 산출물 덮어쓰기 금지 — 기존 brief 존재 시 `.{N}.md` suffix 보존 |
| G21 | secret env 변수 노출 금지 (API key / token / 계좌번호 / chat id) |

---

## Forbidden Language Enforcement

두 source를 최종 redact pass에서 substring 검사:

1. **bootstrap.md Section 3** — forbidden language 표 전체:
   - Recommendation 차단: "should buy/sell", "looks bullish/bearish", "guaranteed", "sure thing", "no-brainer", "must hold", "long-term winner", "undervalued" (단독), "set to rise/fall"
   - Statistical 차단: "outperformed the market", "alpha confirmed", "strategy proven", "beats benchmark" (N 미충족 시)
2. **`$THRESHOLDS_PATH.enforcement.forbidden_language`** — single source 정량 임계값

매치된 substring은 evidence-based phrasing으로 대체하거나 redact.
