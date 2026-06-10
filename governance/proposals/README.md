# Proposals — Governance 설계 제안 staging

`governance/proposals/` 는 `governance/decisions/`(ADR register)의 **전 단계** staging 영역이다.

## 역할

- 아직 commit 되지 않은 설계 제안, spec draft, 분석 report를 staging
- `decisions/` 승격 전 peer review + feasibility 검증을 위한 작업 공간
- decisions 와 달리 **append-only 강제 없음** — draft 수정 / 폐기 가능

## 생명주기

```
  proposal draft  →  review / feasibility  →  ADR (decisions/) 등록
       ↑                                         │
       └── revise / abandon ──────────────────────┘
```

## decisions/ 와의 관계

| 축 | proposals/ | decisions/ |
|---|---|---|
| 상태 | 임시 draft, 검토 중 | accepted / rejected / superseded (영구) |
| 변경 | 수정·폐기 자유 | append-only, overwrite 금지 (G20) |
| 의미 | "검토 중인 제안" | "확정된 결정" |

## 파일 명명

관행적으로 `{topic}-{date}.md` (예: `architecture-review-findings-2026-06.md`). decisions/ 승격 시 `NNNN-{title}.md` 형식으로 번호 부여.

## 참조

- `../decisions/` — ADR register (proposals 승격 도착지)
- `../decisions/README.md` — ADR 인덱스 및 템플릿
- `../AXIOMS/` — 5대 철학 본문 (변경 빈도 매우 낮음)
- `../../AGENTS.md` — agent context / hard guards
