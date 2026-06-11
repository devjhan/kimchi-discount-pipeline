# Inputs & Output — stage0-regime-labeler

## Inputs (mandatory)

| 우선순위 | 경로 | 누락 시 |
|---|---|---|
| 1 | `$TRAIL_TODAY/00-macro-regime.json` | **즉시 중단** — Stage 0 helper 미실행. 사용자에게 helper 실행 요청 |
| 2 | `$OPERATIONS_DIR/daily-{date_prev_N}/00-macro-regime.json` (최근 30일 7개 sample) | 없으면 trend narrative skip + warning |

## Output Artifact

경로: `$TRAIL_TODAY/00-macro-regime-narrative.md`

기존 파일 존재 시 `.{N}.md` suffix로 보존 (G20).

본문 구조:
- regime label 의미 (예: `late_cycle` = '후기 사이클 진입 의심')
- 각 indicator value의 사이클상 위치 (예: yield curve inversion = 역사적으로 6~18개월 후 침체 빈도 X)
- regime shift 발생 시 `consecutive_days_in_current` 의미 + 이전 regime와의 차이
- cash band 의미 (보수성 vs 공격성)
