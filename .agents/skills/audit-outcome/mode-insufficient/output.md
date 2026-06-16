# Mode B — 누적 부족

## 조건

- `$AUDIT_DIR/shadow-portfolio/state.json` 존재
- but 누적 분기 < 4 (shadow portfolio init 후 1분기 미완료)

## 절차

1. shadow-portfolio/state.json read → 분기 수익률 계산 생략
2. `minimum_quarters_before_check: 4` 미충족 → self-disable check skip

## 산출

- `$AUDIT_DIR/outcome-{YYYY-Q}.md` (간략 버전)

## Verdict

`insufficient_quarters`
