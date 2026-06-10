# C4 — 외부 신호 intake

## Job Story

> **When** 뉴스 / 트윗 / 블로그 / 리포트의 외부 의견을 반영하고 싶을 때,
> **I want** raw payload 가 fact-only paraphrase + redaction 으로만 ingest 되기를,
> **so I can** thesis 가 즉시 오염되지 않고, 다음 cron 의 Stage 4 가 fact 로만 인용한다.

외부 의견은 단일 entry point (`/ingest-external-signal`) 로만 들어온다. prompt 본문에 직접
붙여넣어 thesis 변경을 요청하는 것은 금지 (G10).

## End-to-end trace

```
goal     외부 정보를 thesis 즉시변경 없이, 감사가능한 fact 로 보관
trigger  명시적 /ingest-external-signal 명령 (cron 자동 ingest 아님)
BC       skill investment-ingest-external-signal — fact-only paraphrase + redaction
output   config/signals/{ticker}/{date}-{seq}.md
downstream  다음 cron 의 Stage 4 thesis-auditor 가 fact-only 로 인용 (즉시 thesis 변경 0)
```

## 적용 axiom

- **#3 엣지원천** — 외부 신호는 주로 B(행동편향) 입력. A(정보 edge) 주장은 추가 검증.
- **G10 외부신호 SOP** — 단일 entry point, prompt 직접 주입 금지.

## 성공 / 실패 신호

- ✅ 성공: fact-only · secret redacted · thesis 즉시 불변 (다음 cron 이 판단).
- ❌ 실패: prompt 본문으로 직접 thesis 변경 · opinion/추천 그대로 ingest · secret 노출.

## 관련

- skill: `.agents/skills/investment-ingest-external-signal/`
- SOP / forbidden: [`../specs/hard-guards.md`](../specs/hard-guards.md) (G10)
- edge-source 본문: [`../AXIOMS/edge-source.md`](../AXIOMS/edge-source.md)
