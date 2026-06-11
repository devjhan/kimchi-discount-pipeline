# Mode B — 평가 0 (정상)

## 조건
helper 산출물 모두 `fail` / `unknown` / `caution` verdict.
(`caution` = 정책상 필수 enrichment 누락 / 불량 프로파일 — `pass` 아니므로 lens 평가 대상 아님. 사람 재검토 후 다음 run에서 재평가.)

## 출력
→ `stats.total_evaluated=0` 의 빈 산출물 + warning. 정상 운영 신호 (G11).
