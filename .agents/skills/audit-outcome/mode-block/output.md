# Mode C — State 부재 차단

## 조건

- `$AUDIT_DIR/shadow-portfolio/state.json` 존재하지 않음
- 결정론 엔진(`domains.audit_integrity.main`)이 아직 최초 daily snapshot을 생성하지 않음

## 절차

1. 파일 부재 확인 → 즉시 중단
2. 사용자 안내: "shadow-portfolio/state.json 미발견 — 결정론 엔진이 최초 snapshot을 갱신할 때까지 대기"

## 산출

없음 (report 미생성)
