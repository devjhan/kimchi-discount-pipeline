---
name: context-risk
description: Investment 파이프라인 `domains/risk_engine/` BC 작업 시 domain context 주입. common/ 통합 가이드 파일을 선행 읽기로 안내. 작업 전 invoke 권장.
---

# context-risk

`domains/risk_engine/` BC (Stage 5 Sizing + Monitoring + Account) 코드 작업 전 invoke. 본문은 인덱스 — 상세는 `common/` 파일 참조.

## 선행 읽기

### 공통 (common/)
1. `common/overview.md` — BC 개요, 3 concern (sizing/monitor/account), CLI 진입점 (flat 모듈명 보존 필수), 외부 연결점 테이블, KisAccountPort + G9 type-level read-only, 4 Anchor, 산출물 schema
2. `common/sizing.md` — Sizing: fractional Kelly (quarter), 단일 25% cap (G16), 합산 Kelly 0.5, asymmetry guard (G5), drawdown brake -15% (G17), cash band (G18), G12 portfolio context 보류
3. `common/monitoring.md` — Thesis monitoring: positions store (PositionsStore/F-5b), positions_sync (계좌 read-only), portfolio_state_derive (drawdown/cash), thesis_sync (5a projection), falsifier_proximity (5b), event_falsifier_linker (5c), thesis_expiry (5d)
4. `common/boundaries.md` — DDD 경계: `_boundary.py` 게이트, invariant-C/D GREEN, KIS read-only gateway, KisAccountPort adapter, composition-root 주입 패턴
5. `common/audit.md` — 검증·로깅: in-BC ViolationLog 없음 대신 정적/타입 guard, G-guard 적용표 (G5~G21)
6. `common/config-contract.md` — Config 계약: thresholds.yaml (sizing 키), runtime-policy.yaml (G9), portfolio.yaml (G12), macro-regime.json (G18)

## 핵심 불변식

- **Fractional Kelly 1/4~1/2**: full Kelly 금지, 보수적 분할 배팅 (기하평균 극대화)
- **단일 종목 25% cap (G16)**: 포트폴리오 대비 단일 종목 최대 노출 25% 초과 금지
- **합산 Kelly 0.5 cap (G16)**: 전체 포트폴리오 Kelly 합 ≤ 0.5 — 동시다발 베팅 과잉 방지
- **Drawdown -15% brake (G17)**: peak-to-trough -15% 도달 시 전 포지션 절반 alert (자동 brake, 매매는 수동)
- **현금 ≥ `cash_band[0]` (G18)**: 최소 현금 보유 미달 시 alert, 추가 진입 불가
- **`KisAccountPort` type-level read-only**: port surface 에 order/submit/cancel 메서드 부재 → 매매 호출이 타입상 불가능 (G9 4번째 구조 가드)

## 전형적 실패 패턴

- Kelly f 독립 가정 무시: 여러 종목의 Kelly f 를 단순 합산 → 상관관계 무시로 과대 배팅 (합산 cap 0.5 가 hard guard)
- Drawdown brake 미적용: -15% 도달했는데 sizing 그대로 출력 → G17 위반
- `USER_PORTFOLIO_TOTAL_KRW` 없이 사이즈 출력: 포트폴리오 context 미입력 상태에서 KRW 절대금액 산출 → G12 위반 (사이즈 보류)
- 물리 concern 서브패키지 reorg 시도: `sizing/` `monitor/` `account/` 디렉토리 분리 → ADR-0007 기각됨 (재제안 금지)

## 산출물

- `$TRAIL_TODAY/05-sizing-recommendation.json` — Stage 5 사이징 권고
- `$TRAIL_TODAY/05a-thesis-sync.json` — thesis sync (projection)
- `$TRAIL_TODAY/05b-falsifier-proximity.json` + `drift-{date}.md` — falsifier 근접도
- `$TRAIL_TODAY/event-trigger-status-{date}.json` — event trigger 평가
- `$TRAIL_TODAY/05d-thesis-expiry.json` + `expiry-{date}.md` — thesis 만기
- `$POSITIONS_DIR/_summary-{date}.json` + `_derived-{date}.json` — 계좌 sync/파생

## Out of Scope

- 다른 BC 의 책임 — macro / screener / catalyst / universe 내부 import 금지
- 실제 KIS 매매 체결 — G9 절대 금지 (`KisAutoTradeBlocked`)
- Thesis 작성 — Stage 4 skill `stage4-thesis-auditor` 책임
