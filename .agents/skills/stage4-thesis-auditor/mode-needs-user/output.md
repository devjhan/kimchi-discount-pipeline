# Mode B — 사용자 확인 필요

## 조건 (하나라도 해당)
- Stage 3 산출물 (`03-catalyst-events.json`) 누락
- Stage 2 산출물 (`02-quality-filter.json`) 누락 + Stage 3에 후보 1+ 존재
- 기존 보유 포지션 amendment에서 falsifier / edge_source / time_horizon 변경 발생
- accepted 후보에 A claim이 있고 confirmation_bias_check를 본 skill이 단독으로 답할 수 없음
- `$THRESHOLDS_PATH`의 thesis 섹션이 없거나 schema mismatch

## 출력
→ JSON 산출 보류 + 사용자에게 묶음 질문 escalation.

질문 형식:
```
다음 항목에 대한 사용자 결정이 필요합니다:

Q1. ...
Q2. ...
```
