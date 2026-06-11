# Proposals — 제안 draft (ADR 승격 전 staging)

> **원본**: `governance/proposals/*.md` (5파일)
> **본 파일**: agent-readable 인덱스. draft — 수정·폐기 자유, append-only 강제 없음.

| 제안 | 주제 | 핵심 결론 |
|---|---|---|
| `agent-harness-remediation-plan-2026-06` | Skill-First Context Injection + 100줄 하드캡 설계 | ADR-0011 로 승격 완료. 8종 Context Skill + 기존 9종 재구성 계획 |
| `architecture-review-findings-2026-06` | Architecture review findings (잔여) | F-2(legacy threshold 제거), F-4(policy drift gate), F-11(2-layer profile), Wave 5(hexagonal) |
| `batch-fetch-and-profile-authoring-review-2026-06` | 배치 fetch / LLM 프로파일 작성 효율성 | 배치 fetch 불필요(steady-state 캐시 흡수). cold-start = 진짜 gap |
| `graphify-plugin-roi-2026-06` | Graphify 플러그인 도입 ROI | ROI 음수에 가까운 저양수. 비용 0이나 편익도 0 — 보류 권고 |
| `parallelization-roi-2026-06` | 병렬화 ROI (fetch + profile) | 둘 다 ROI 음수. universe 협소화·순차 러너가 더 싸고 안전한 대안 |

## 상태

- `agent-harness-remediation-plan-2026-06`: **승격 완료** → ADR-0011
- `architecture-review-findings-2026-06`: 검토 중 — 잔여 finding 3건 (F-2, F-4, F-11)
- `batch-fetch-and-profile-authoring-review-2026-06`: read-only findings — actionable 후보 추출 완료
- `graphify-plugin-roi-2026-06`: **권고: 보류** (재검토 예약)
- `parallelization-roi-2026-06`: **권고: 병렬화 불채택** (순차 러너 채택)
