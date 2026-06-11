# Agent Context: Retail Investment Pipeline (Korean Special Situations)

> **Skill-First Context Injection**. 작업 전 해당 Context Skill invoke 권장.
> `AGENTS.md` 본문은 **인덱스** 역할 — 상세는 각 skill의 `SKILL.md` + `domain/` 참조.

---

## Quick Reference — Skill Index

| 하려는 작업 | invoke |
|---|---|
| governance 규칙 / 코딩 컨벤션 조회 | `/context-governance` |
| `domains/macro/` (Stage 0) 코드 | `/context-macro` |
| `domains/universe/` (Stage 1) 코드 | `/context-universe` |
| `domains/screener/` (Stage 2) 코드 | `/context-screener` |
| `domains/catalyst/` (Stage 3) 코드 | `/context-catalyst` |
| `domains/risk_engine/` (Stage 5) 코드 | `/context-risk` |
| `domains/policy/` (Enrich-Cutoff) 코드 | `/context-policy` |
| `domains/audit_integrity/` 코드 | `/context-audit` |
| Stage 2 정성 lens 평가 | `/stage2-quality-lens` |
| Stage 4 thesis 작성/검증 | `/stage4-thesis-auditor` |
| Stage 6 daily brief 합성 | `/stage6-brief-author` |
| 주간 process audit | `/audit-process` |
| 분기 outcome audit | `/audit-outcome` |
| 외부 신호 ingest | `/ingest-external-signal` |
| Enrich-Cutoff profile draft | `/policy-profiler` |

---

## 5대 철학 (1줄 요약)

| # | 철학 | 1줄 |
|---|---|---|
| 1 | 생존 최우선 | 기하평균 극대화 — 단일 종목 25% cap, fractional Kelly, drawdown -15% brake |
| 2 | 반증 가능성 | 모든 thesis는 구체적 falsifier 강제 (time-cap / metric-trigger / event-trigger) |
| 3 | 엣지 원천 명시 | C(구조) + D(시간) 이 본질적 edge — A(정보) 인용 시 추가 검증 |
| 4 | 비대칭 손익비 | downside_floor / upside_ceiling 비율 < 2 → reject 또는 size 절반 cap |
| 5 | 통계적 정직성 | N < 10: 주장 금지 / 10≤N<30: 부호만 / 30≤N<100: p<0.10 / N≥100: p<0.05 |

---

## Hard Guards (축약)

| ID | 룰 | 위반 시 |
|---|---|---|
| G1 | Falsifier 없는 thesis reject | verdict=rejected |
| G2 | Falsifier 3 카테고리 강제 | category 외 reject |
| G3 | 5필드 누락 시 reject | 누락 필드별 reject |
| G4 | A 단독 인용 시 추가 검증 | information_edge_evidence 강제 |
| G5 | asymmetry_score < 2 → reject/절반 cap | high_conviction_eligibility=false |
| G6 | 정량 계산 helper 위임 | LLM 직접 계산 금지 |
| G7 | 모든 숫자 helper citation | `{source}@{ts}={value}` 형식 |
| G8 | 미취득 데이터 추측 금지 | hallucination 최고 severity |
| G9a | 자동 매매 금지 | `AGENT_BLOCK_AUTO_TRADE=true` 불변 |
| G10 | 외부 신호 `/ingest-external-signal` 만 | prompt 직접 채택 금지 |
| G11 | Default = no action | 새 후보 강제 생성 금지 |
| G12 | Portfolio context 미입력 → 사이즈 보류 | USER_PORTFOLIO_TOTAL_KRW 필요 |
| G13 | Quality filter 우회 금지 | quality fail 종목 진입 금지 |
| G14 | Universe 자동 추가 금지 | manual_additions 만 허용 |
| G15 | d_type 단독 trigger 금지 | A/B-type 결합 필요 |
| G16 | 단일 종목 25%, 합산 Kelly 0.5 cap | 초과 시 reject |
| G17 | Drawdown -15% → 전 포지션 절반 alert | 자동 brake |
| G18 | 현금 ≥ cash_band[0] | 미만 시 alert |
| G19 | Sample size gate wording | N<30: alpha 주장 금지 |
| G20 | 산출물 덮어쓰기 금지 | `.{N}` suffix 보존 |
| G21 | Secret 노출 금지 | .env 값 본문/로그/표준출력 금지 |
| G22 | Raw payload redact 후 저장 | 원본 보존 금지 |

---

## 경로 해석

| shorthand | 실제 경로 (repo root 기준) |
|---|---|
| `$TRAIL_TODAY` | `operations/{KST 거래일}` |
| `$AUDIT_DIR` | `telemetry/audit` |
| `$POSITIONS_DIR` | `telemetry/positions` |
| `$EXTERNAL_SIGNALS_DIR` | `config/signals` |
| `$POLICY_DRAFTS_DIR` | `telemetry/policy_drafts` |
| `$PROFILES_DIR` | `governance/profiles` |
| `$THRESHOLDS_PATH` | `governance/thresholds.yaml` |
| `$AXIOMS_DIR` | `governance/AXIOMS` |

---

## 주요 디렉토리

| 디렉토리 | 역할 |
|---|---|
| `governance/` | 선언적 정책 (AXIOMS, directives, decisions, proposals, thresholds, profiles) |
| `domains/` | 기계적 실행 — BC별 Python (macro, universe, screener, catalyst, risk_engine, policy, audit_integrity) |
| `infrastructure/` | 외부 I/O (DART, KIS, Yahoo, FRED, notify, scheduling, _common/utils.py) |
| `operations/` | 일별 파이프라인 산출물 (`{YYYY-MM-DD}/`) |
| `telemetry/` | cross-day 감사·관측 (audit, positions, nav-history, logs, policy_drafts) |
| `config/` | 사용자 입력 (user/, signals/) |
| `applications/` | 실행 진입점 (run_daily_local.sh, daily_pipeline.sh) |
| `.agents/skills/` | Zed project-local skills |

---

## Forbidden Language

산출물 본문에 다음 금지:
- **Recommendation**: "should buy/sell", "looks bullish/bearish", "guaranteed", "sure thing", "must hold", "long-term winner"
- **Statistical** (N 미충족 시): "outperformed", "alpha confirmed", "strategy proven", "beats benchmark"
- **Vague**: "undervalued" 단독, "set to rise/fall"
- **Unsourced numbers**: 모든 숫자는 `{source}@{ts}={value}` citation 강제

---

## Default = No Action

대부분의 cron 실행에서 새 후보 0, falsifier 미발동이 정상. 일주일 변화 0 = 정상 신호.

## 외부 신호 SOP

뉴스/트윗/블로그/리포트 → `/ingest-external-signal` 명령으로만 ingest. prompt 직접 채택 금지.

## Disclaimer

본 시스템은 자기 자본의 personal research tool이며, investment advice가 아니다. 모든 진입/청산은 사용자 manual 실행. 결과 책임은 사용자에게 있다.
