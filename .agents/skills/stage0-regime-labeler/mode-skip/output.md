# Mode B — Narrative Skip (정상)

## 조건
helper 산출물에 모든 indicator value=null (regime=unknown). FRED API 등 미가용 상태.

## 출력
→ narrative 작성 보류. 사용자에게 안내 메시지:
"FRED_API_KEY 또는 manual breadth 입력 후 재실행"

## 상태
정상 운영 신호 (G11). 강제로 narrative 생성 금지.
