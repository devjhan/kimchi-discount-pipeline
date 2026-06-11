# Mode C — 차단

## 조건
helper 산출물 자체가 missing (`$TRAIL_TODAY/00-macro-regime.json` 없음).

## 출력
→ 즉시 중단 + 사용자에게 helper 실행 요청 안내.
Stage 0 helper (`stage0-macro-regime.py`) 먼저 실행 후 재시도.
