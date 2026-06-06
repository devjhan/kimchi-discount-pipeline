# ADR-0007 — risk_engine: 물리 concern 서브패키지 reorg 기각

`status: Rejected-proposal`
`date: 2026-06-06`
`refs: D-ARCH-2, domains/risk_engine/AGENTS.md`

## Context

`risk_engine` 은 3 concern (sizing / monitor / account) 을 담는다. 이를 *물리 서브패키지*
(`sizing/ monitor/ account/`) 로 분리해 더 "정돈" 하자는 제안이 나왔다.

## Decision

**기각.** `domain/` + `application/` 레이어 + flat CLI shim 이 이미 BC 골격을 충족한다.
concern 축을 물리 디렉토리로 더하면:

- 2D 디렉토리 (concern × layer) 복잡도,
- `positions_sync` 등 byte-diff,
- `daily_pipeline.sh` 하드코딩 경로 churn

대비 이득이 cosmetic 하다. `audit/` 서브패키지도 미추가 (risk_engine 은 ViolationLog 기록
need 부재 — `cash_band_violation` 은 sizing payload flag 일 뿐). `config/` 지역화도 보류
(sizing 가드 Kelly fraction/cap 은 `governance/thresholds.yaml` *doctrine* 이라 잔류가 정합
— [ADR-0002] 존중).

## Consequences

- 3 concern 은 *논리 축* (문서 표) 으로만 유지, 물리 디렉토리는 layer 축만.
- 이 판단은 "맹목 지역화 금지 / YAGNI" 의 사례 → [D-ARCH-2].

## Alternatives considered

- **물리 concern reorg + per-BC audit/·config/** — 기각 (위). churn > 이득, need 부재.

## Supersedes / Superseded-by

(없음. 재제안 방지 기록 — 재논의 시 본 ADR 의 비용 분석을 반증할 새 근거 필요.)
