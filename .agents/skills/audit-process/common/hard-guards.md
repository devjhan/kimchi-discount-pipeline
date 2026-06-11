# Hard Guards — audit-process

| ID | 적용 |
|---|---|
| G6 | audit이 사이즈 / 비율 재계산 시도 금지 (산출물 read-only) |
| G7 | violation 사례에 정확한 file path + line number 인용 강제 |
| G20 | audit-report 덮어쓰기 금지 |
| G21 | secret 노출 검사 자체에서 secret 본문 audit-report에 인용 금지 (예: "AP-9: secret value=AAAA" 같은 본문 절대 금지. 위치만 명시) |
