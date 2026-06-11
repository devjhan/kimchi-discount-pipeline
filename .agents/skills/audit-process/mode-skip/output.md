# Mode B — 산출물 부재 (skip)

## 조건

- 해당 주 일별 산출물 0건 (cron run 미실행 또는 전부 missing)

## 절차

1. scan 결과 0건 확인 → 즉시 skip
2. report 경량화 (violation 테이블 생략)

## 산출

- `$AUDIT_DIR/process-{YYYY-WW}.md` (경량)

## Verdict

`skipped`
