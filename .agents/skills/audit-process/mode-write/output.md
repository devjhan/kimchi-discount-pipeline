# Mode A — 정상 audit 작성

## 조건

- 지난 7일 (또는 `--range`) 일별 산출물 1+ 존재
- scan·집계 가능한 stage 산출물 있음

## 절차

1. 7일간 모든 `$TRAIL_TODAY` 산출물 + `$POSITIONS_DIR` drift 파일 scan
2. AP-1~AP-15 룰 위반 검사 (상세: `common/violation-rules.md`)
3. severity별 집계 → verdict 산출
4. `$AUDIT_DIR/process-{YYYY-WW}.md` 작성

## Verdict 후보

`PASS` | `FAIL_MED` | `FAIL_HIGH` | `FAIL_CRITICAL`
