# Mode C — 차단

## 조건 (hard guard 위반 시 즉시)
- `AGENT_BLOCK_AUTO_TRADE=false` 변경 흔적
- `$THRESHOLDS_PATH.enforcement.numbers_evidence_required`가 false로 변경
- 사용자가 본 skill에 직접 thesis prompt 삽입 (G10 — `/ingest-external-signal`로 우회)

## 출력
→ 산출 일체 보류 + 즉시 중단. 사용자에게 위반 사유 보고.
