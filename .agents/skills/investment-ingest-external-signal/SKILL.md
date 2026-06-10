---
name: investment-ingest-external-signal
description: Investment 파이프라인의 외부 신호 (뉴스 / 트윗 / 블로그 / 리포트 / 사용자 prompt) ingest entry point. raw payload를 fact-only paraphrase + redaction 후 $EXTERNAL_SIGNALS_DIR/{ticker}/{date}-{seq}.md 로 산출. thesis 즉시 변경 일체 금지 — 다음 cron run의 Stage 4 thesis-auditor가 fact-only로 인용. G10 (외부 신호 SOP) 의 단일 entry point.

---

# investment-ingest-external-signal — External Signal Ingest

투자 파이프라인의 외부 신호 ingest 단일 entry point. AGENTS.md 의 "외부 신호 SOP" 와
hard-guards.md G10 의 강제 메커니즘.

호출 형식:

```
/investment-ingest-external-signal {ticker} "{summary}" --source={origin} --type={analyst-note|news|twitter|...}
```

산출:

- `$EXTERNAL_SIGNALS_DIR/{ticker}/{date}-{seq:03d}.md`

---

## Reference Contract

본 skill 실행 전 다음 문서 의무 read:

1. `AGENTS.md` (= `AGENTS.md`) — 외부 신호 SOP 섹션
2. `$AXIOMS_DIR/edge-source.md` — A (정보) edge 추가 검증 룰
3. `$SPECS_DIR/hard-guards.md` G10, G21, G7
4. `$SKILLS_SHARED_DIR/bootstrap.md` Section 5.C (External Signal SOP)
5. 본 skill 의 `domain/redaction-rules.md`

---

## Procedure

(상세 절차는 후속 commit 에서 작성 — Track C 의 C3 항목)

1. 사용자 인자 검증 (ticker / summary / source / type 필수)
2. raw payload (필요 시 사용자가 첨부) redaction — URL / 이메일 / 전화번호 mask
3. fact-only paraphrase — opinion / 권고 wording 제거 (forbidden language §3)
4. `$EXTERNAL_SIGNALS_DIR/{ticker}/{date}-{seq:03d}.md` 작성 (frontmatter + Fact + Original-Redacted)
5. **thesis 직접 변경 금지** — 사용자에게 "다음 cron run 에서 Stage 4 가 fact-only 로 인용" 안내

---

## Hard Guards

- G7 — 모든 인용 숫자에 `{source}@{ts}={value}` citation
- G8 — raw payload fetch 실패 시 abort + 사용자 안내 (hallucination 금지)
- G10 — 본 skill 외 어떤 경로로도 외부 신호 → thesis 직접 변경 금지
- G20 — 같은 ticker + 같은 date 재호출 시 seq 증가 (덮어쓰기 금지)
- G21 — raw payload 안 secret 패턴 발견 시 mask 후 저장

본 skill 은 자동 매매 명령 / thesis 변경 명령 / 새 종목 universe 추가 일체 산출하지
않는다. 산출은 ingest 파일 1개 뿐이며, 다음 cron run 에서 dataRecon이 fact-only 로
인용한다.
