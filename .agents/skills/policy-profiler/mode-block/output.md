# Mode C — 차단 (즉시 중단 + 사유 보고)

## 조건 (하나라도 해당)

- 사용자가 본 스킬에 직접 profile/thesis prompt 삽입 (G10 — `/ingest-external-signal` 우회)
- 사용자가 본 스킬로 commit/drift/version 을 수행하라 요청 (F-10 위반 — `--commit-draft` 결정론 안내)
- secret env 값 노출 시도 (G21)

## 절차

1. 즉시 중단
2. 사유 보고 (사용자에게 어떤 룰을 위반했는지 명시)
3. G10 위반 시 `/ingest-external-signal` 경로 안내
4. F-10 위반 시 `python -m domains.policy.main --commit-draft` 결정론 안내

## 산출

없음 (abort)
