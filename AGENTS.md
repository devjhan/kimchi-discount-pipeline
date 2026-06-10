# Agent Context: Retail Investment Pipeline (Korean Special Situations)

## 프로젝트 개요

Retail 투자자 + agent 파이프라인의 결합으로, institutional이 구조적으로 진입하기 어려운 **한국 특수상황 universe** (지주사 / 우선주 / 분할 / 자사주 소각 / 행동주의 진입)에서 1~3년 보유 horizon으로 alpha를 추구하는 시스템. 일단위 cron으로 자동 실행되며, 사용자에게 추천을 제공하되 **최종 결정은 사용자가 한다**.

본 시스템은 **investment advice가 아니다**. 모든 산출물은 사용자 본인의 자본 운용을 위한 personal research tool이며, 외부 공유 / 타인 의사결정 영향 / 자동 매매 체결 모두 범위 밖이다.

---

## 5대 철학 (Five Axiomatic Principles)

본 시스템의 모든 design decision은 다음 다섯 사상에서 도출된다. 사상 위반은 코드 / config / 산출물 어느 layer에서도 허용되지 않는다.

### 1. 생존 최우선 (Survival above Optimization)

비-에르고딕 과정에서 시간평균 < 앙상블평균. 한 번의 ruin은 absorbing barrier — 회복 불가. 따라서 expected return 최대화가 아닌 **기하평균 최대화**를 추구한다.

- 모든 사이즈는 fractional Kelly (1/4 ~ 1/2)로 제한
- portfolio 차원 drawdown circuit breaker (-15% 도달 시 전 포지션 사이즈 자동 절반 alert)
- 단일 종목 25% cap, 합산 Kelly 0.5 초과 금지
- 현금 100% 유지가 valid output. **대부분의 날에 새 후보 0이 정상**

### 2. 반증 가능성 (Falsifiability — Popper for Thesis)

Thesis는 반증 trigger 없이는 thesis가 아니라 **narrative**다. 모든 진입 thesis는 다음 3 카테고리 중 하나의 구체적 falsifier 강제:

- **Time-cap**: "X개월 내 catalyst Y 발생 안 하면 exit"
- **Metric-trigger**: "구체 지표 Z가 W 이하/이상 도달 시 exit"
- **Event-trigger**: "구체 event V 발생 시 exit"

vague falsifier ("실적 안 좋으면", "thesis 깨지면", "전망 나빠지면")는 자동 reject. 보유 포지션의 falsifier proximity는 일단위 monitoring.

### 3. 엣지 원천 명시 (Edge Source Articulation)

"왜 시장이 틀렸는가"라는 inverse question에 답하지 못하면 thesis 아님. 모든 thesis는 다음 4 분류 중 1+ 명시:

- **A. 정보 edge**: 시장보다 잘 안다 (retail에 거의 false; 추가 검증 강제)
- **B. 행동 edge**: 시장이 편향에 빠짐 (recency, narrative, panic-selling)
- **C. 구조 edge**: institutional이 못 산다 (사이즈, IPS, 유동성, 한국어, 회계 특수성)
- **D. 시간 edge**: 내 horizon이 길다 (분기 P&L 압박 없음)

본 시스템의 본질적 edge는 **C + D의 결합**. A를 인용하는 thesis는 confirmation bias 가능성으로 추가 검증.

### 4. 비대칭 손익비 (Asymmetric Payoff)

모든 thesis는 `downside_floor / upside_ceiling` 비율 강제.

- 비율 < 2 (예: -50% 가능 / +100% 미만) → reject 또는 size 절반 cap
- Portfolio 차원 barbell — safe sleeve (현금 + 단기채 + low-vol 배당) vs optional sleeve (high-conviction asymmetric bet) vs middle sleeve (medium-vol broad-market) 비중 cap
- "potential" 단독 인용 금지. downside floor 측정 누락 = thesis 거부

### 5. 통계적 정직성 (Statistical Honesty)

Sample size hard rule:

| N (closed trades) | 허용 표현 |
|---|---|
| N < 10 | `INSUFFICIENT_SAMPLE — alpha 주장 금지` |
| 10 ≤ N < 30 | `DIRECTIONAL_SIGNAL — 부호만 인용` |
| 30 ≤ N < 100 | `WEAK_SIGNAL — t-stat 인용 시 p<0.10 필요` |
| N ≥ 100 | `MEANINGFUL_SIGNAL — p<0.05 표준` |

분기/연간 outcome benchmark (Index / Mechanical / LLM-Filtered / Random 4-tier shadow portfolio) 비교로 LLM filter의 부가가치 검증. 4분기 연속 mechanical > LLM filter면 self-disable trigger 발동.

---

## 아키텍처 요약

```
[Cross-cutting Enforcement — 모든 layer 적용]
  Falsifiability / Asymmetry / Statistical Honesty
  → required field / forbidden language / sample size gate

[Conceptual Constraint Hierarchy — 검증 순서]
  L1 생존 / Macro Regime (E)         → cash band 결정
    L2 보유 가능성 / Quality (C)     ┐
    L3 사냥터 / Universe (A)         │ A ∩ C
      L4 방아쇠 / Catalyst (Event)
        - A-type: 자사주 소각 / 분할 / NAV 좁힘
        - B-type: forced selling / 인덱스 편출 / panic
        - D-type: insider cluster / 행동주의 follow

[Pipeline Execution Sequence — 일별 cron 계산 순서]
  Stage 0  Macro Regime Gate (E)
  Stage 1  Universe Refresh (A)
  Stage 2  Quality Filter (C ∩ A)
  Stage 3  Catalyst Event Scan
  Stage 4  Thesis Discipline Gate
  Stage 5  Sizing Recommendation (E sizing budget 적용)
  Stage 6  Brief Author
```

상세 계층 정의 / forbidden language / hard guard는 `governance/specs/hard-guards.md` 참조.
파이프라인 전체 흐름은 `governance/pipeline-overview.md` 참조 (인간용 reference).
사용자 의도(job story) + capability→system trace 는 `governance/capabilities/`, 구조 결정 근거(ADR)는 `governance/decisions/` 참조.

---

## 기술 스택

| 영역 | 기술 |
|---|---|
| Domain helpers | Python 3.11+ (`domains/{macro, universe, screener, catalyst, risk_engine, policy, audit_integrity}/*.py`) — 각 BC 는 `_boundary.py` 단일 외부 게이트 |
| Filing API | DART (한국, 필수) + EDGAR (미국, 옵션) |
| Market data | KIS API + Yahoo Finance + FRED |
| Config | YAML (`governance/thresholds.yaml`) + dotenv (`.env`) |
| Path 해석 | `infrastructure/_common/utils.py` path helper (`trail_dir()` / `audit_dir()` / `positions_dir()` 등, `$TRAIL_TODAY` 등 env override 우선). 중앙 topology alias SSoT 는 제거됨 — operations/governance 레이아웃은 utils.py 에 단일 정의. |
| Storage | 일별 산출물 `operations/{date}/` (markdown+JSON) + cross-day 상태·증거 `telemetry/` (audit/positions/nav-history/logs/policy_drafts) + 사용자 config `config/` (user/signals) + 재생성 캐시 `.cache/` + 자격증명 `secrets/` |
| Notification | `infrastructure/notify/` dispatcher (Slack / Gmail / Telegram / Discord / Kakao / Webhook outbound 어댑터, `python -m infrastructure.notify.dispatcher`) — `applications/run_daily_local.sh` 가 딥시크 API + Python notify adapter로 발송 |
| Scheduling | **로컬 launchd (macOS) primary** — `governance/schedules.yaml` (SSoT), `infrastructure/scheduling/launchd_generator.py` 가 plist emit, `infrastructure/scheduling/install.sh` 가 OS 경계 단일 통로. cloud routine 은 `governance/deployment-residency.md` §3 조건 충족 시에만 fallback — 현재 KIS/DART/KRX IP 차단으로 비활성 (cloud_routine_run.sh deprecated). 사용자 수동 invoke 도 가능. crontab 등 시스템 자동 cron 은 여전히 금지 — 모든 자동화는 launchd LaunchAgent 경유. 헌법: `governance/deployment-residency.md`. |
| Agent runtime | Zed Agent project skills (`$SKILLS_DIR/investment-*`, `.agents/skills/`). DeepSeek API (`api.deepseek.com`, OpenAI-compatible) — `infrastructure/llm/deepseek.py` adapter |
| Hard guards | `governance/decisions/0027-hook-disposition.md` (Claude Code hook 7종 파기 + 대체 수단 기록). Pre-commit lint + pipeline validation |

---

## 디렉토리 구조

```
investment_v3/
├── AGENTS.md                # canonical 에이전트 컨텍스트 (본 문서)
├── governance/              # 선언적 정책 — Python 코드와 분리된 입법부
│   ├── AXIOMS/              # 5 철학 본문 (대문자 강조 — 변경 빈도 매우 낮음)
│   │   ├── ergodicity.md
│   │   ├── falsifiability.md
│   │   ├── edge-source.md
│   │   ├── asymmetry.md
│   │   └── statistical-honesty.md
│   ├── capabilities/        # 의도 layer (누구에게/무슨 결과) — capability map + job story (README + C1~C6)
│   ├── decisions/           # ADR register — 구조 결정 영구 ledger (append-only, README + NNNN-*.md)
│   ├── specs/               # stage 가 만족해야 하는 계약
│   │   └── hard-guards.md   # G1-G21 hard guard 정의 + forbidden language
│   ├── procedures/          # runtime / manual invoke 절차
│   ├── directives/          # 코딩 컨벤션 D-{LANG}-{N} + D-ARCH 아키텍처/배치 판단 기준 (AGENTS.md 인덱스)
│   ├── profiles/            # 종목별 Enrich-Cutoff 프로파일 SSoT (git-tracked)
│   ├── thresholds.yaml      # 정량 임계값 SSOT
│   ├── schedules.yaml       # scheduler SSoT (launchd plist 생성 source) + schedules.lock.yaml
│   ├── runtime-policy.yaml  # G9 정적 enforcement (block_auto_trade / KIS read-only whitelist)
│   └── pipeline-overview.md # 인간용 파이프라인 reference / index
├── domains/                 # 기계적 실행 — bounded contexts (행정부, 각 BC 는 _boundary.py 게이트)
│   ├── macro/               # Stage 0/0a (regime / breadth) BC
│   ├── universe/            # Stage 1 (universe build: sources + enrichers plugin) BC
│   ├── screener/            # Stage 2 (quality filter: Rule tree) BC
│   ├── catalyst/            # Stage 3 (catalyst scan: 6 detector plugin, 구 alpha_factory) BC
│   ├── risk_engine/         # Stage 5/5a/5b/5c/5d + positions_sync + portfolio_state_derive (sizing/monitoring) BC
│   ├── policy/              # Enrich-Cutoff profile commit governance BC
│   ├── audit_integrity/     # 4-tier shadow portfolio (paper trade only) + stat_tests
│   ├── _shared/             # 공유 커널 (audit / profile_registry / positions_store / time)
│   └── brief_gate/          # Stage 6 schema validators (순수 read-only 검증 — notify 는 infrastructure/notify/)
├── infrastructure/          # 외부 I/O 격리 — DDD infrastructure layer
│   ├── _common/utils.py     # 공유 utility (path helper / I/O / citation / G20 / env / runtime-policy / 거래일)
│   ├── scheduling/          # launchd_generator + install.sh (schedules.yaml → plist, OS 경계 단일 통로)
│   ├── dart/client.py       # OPEN DART API client + subsidiaries/preferred_pairs parser
│   ├── kis/client.py        # KIS API client (시세 read + 계좌 read-only whitelist, 매매/주문 3중 차단)
│   ├── yahoo/client.py      # Yahoo Finance public chart endpoint (KIS fallback)
│   ├── fred/client.py       # FRED 지표 fetch (DGS10/DGS2/BAML HY/VIX)
│   ├── notify/              # outbound 알림 어댑터 (dispatcher + slack/gmail/telegram/discord/kakao/webhook)
│   └── krx/refresh_holidays.py     # KRX 휴장일 자동 fetch
├── operations/              # 일별 파이프라인 산출물 전용 (2026-06-02 재편)
│   └── {YYYY-MM-DD}/        # 일별 stage 산출물 + daily-brief.md (+ _notify-results.json)
├── applications/            # 실행 진입점 (구 scripts/ + operations/cron/ 합류)
│   ├── bootstrap.sh         # repo-local venv 초기화
│   ├── run_daily_local.sh   # launchd primary 진입점 (manual invoke 도 가능)
│   ├── daily_pipeline.sh    # Stage 0~5 deterministic orchestrator (phase 분리)
│   └── cloud_routine_run.sh # [deprecated] cloud routine orchestrator
├── telemetry/               # cross-day 감사·관측 데이터
│   ├── audit/               # 날짜-prefix flat 파일 (shadow-portfolio-state / trade-log / scheduler-state / {domain}-violations / macro-breadth / subsidiaries) — 추적 (현재 .gitkeep, 파이프라인 활성 시 누적)
│   ├── positions/           # 보유 포지션 state (per-ticker thesis/drift/balance/expiry — 추적)
│   ├── nav-history/         # NAV 시계열 (Σ 자회사 시총×지분율 — 재생성-불가 증거, 추적)
│   ├── logs/                # cron / launchd / hook 실행 로그 (gitignore)
│   └── policy_drafts/       # commit 전 ephemeral policy draft (gitignore)
├── config/                  # 사용자·입력 config성 데이터
│   ├── user/                # portfolio.yaml / behavior.yaml (gitignore — .example 추적)
│   └── signals/             # /ingest-external-signal 산출 + macro/breadth.yaml (Stage 0a)
├── .cache/                  # 재생성 가능 캐시 (gitignore, 숨김): dart / financials
├── secrets/                 # API 자격증명 (.kis_token.json — gitignore, chmod 0600)
├── .agents/
│   └── skills/              # Zed project-local skills
│       ├── contract/             # cross-cutting bootstrap 규약 (bootstrap.md)
│       ├── investment-stage0-regime-labeler/  # Stage 0 LLM narrative labeler
│       ├── investment-stage2-quality-lens/    # Stage 2 정성 lens 평가
│       ├── investment-stage4-thesis-auditor/  # Stage 4 thesis discipline gate (+ domain/)
│       ├── investment-stage6-brief-author/    # Stage 6 daily brief author
│       ├── investment-audit-process/          # 주간 process audit
│       ├── investment-audit-outcome/          # 분기 outcome audit
│       ├── investment-ingest-external-signal/ # 외부 신호 ingest
│       └── investment-policy-profiler/        # Policy profile research
├── .env              # API keys (gitignore — 사용자가 manual 복사)
└── .gitignore
```

### 경로 해석 (path helpers)

중앙 topology alias SSoT (`topology.yaml` + `from_alias` + `resolve_aliases` hook) 는 제거됐다.
경로는 도메인 코드가 `infrastructure/_common/utils.py` 의 path helper 로 직접 계산하며,
operations/governance 레이아웃은 utils.py 에 단일 정의된다. 각 helper 는 대응 env var
(예: `$TRAIL_TODAY`) 가 set 이면 우선 사용 — 테스트(conftest monkeypatch) / cron / cloud override 용.

BC 도메인 (macro/screener/universe/policy)은 `_boundary.py` 의 `resolve_path()` / `resolve_trail_dir()`
단일 게이트를 통과한다. SessionStart 의 "주요 경로" 블록에 오늘 KST 실제 절대경로가 출력된다.

| helper / shorthand | 실제 경로 (repo root 기준) |
|---|---|
| `trail_dir(date)` / `$TRAIL_TODAY` | `operations/{KST 거래일}` |
| `audit_dir()` / `$AUDIT_DIR` | `telemetry/audit` |
| `positions_dir()` / `$POSITIONS_DIR` | `telemetry/positions` |
| `nav_history_dir()` / `$NAV_HISTORY_DIR` | `telemetry/nav-history` |
| `external_signals_dir()` / `$EXTERNAL_SIGNALS_DIR` | `config/signals` |
| `policy_drafts_dir()` / `$POLICY_DRAFTS_DIR` | `telemetry/policy_drafts` |
| `repo_path(".cache", …)` (캐시) / `repo_path("secrets", …)` (시크릿) | `.cache/…` / `secrets/…` |
| `profiles_dir()` / `$PROFILES_DIR` | `governance/profiles` |
| (literal) `$AXIOMS_DIR` / `$SPECS_DIR` / `$THRESHOLDS_PATH` | `governance/AXIOMS` / `governance/specs` / `governance/thresholds.yaml` |
| `$ENV_PATH` | `.env` |

doctrine 본문의 `$ALIAS` 표기는 readable shorthand 이며, 그 의미는
.agents/skills/contract/bootstrap.md` 의 "경로 표기" 레전드에 정의돼 있다.

---

## Hard Guards (G1-G22)

본 섹션의 룰 위반은 어떤 작업 / 어떤 cron run / 어떤 사용자 명령으로도 우회 불가하다. 위반 발견 시 즉시 작업 중단 + 사용자 보고.

### G1-G5: Thesis 작성

- **G1**: Falsifier (손절 조건) 없는 thesis는 무조건 reject. vague falsifier ("실적 안 좋으면", "thesis 깨지면", "전망 나빠지면") 자동 reject.
- **G2**: Falsifier는 다음 3 카테고리 중 1+ 강제: (a) time-cap (b) metric-trigger (c) event-trigger.
- **G3**: 5필드 (entry_catalyst / falsifier / time_horizon_months / edge_source / asymmetry_score) 누락 시 reject.
- **G4**: edge_source가 A (정보 edge) 단독 인용 시 confirmation bias 추가 검증 강제. retail에 정보 edge는 거의 false.
- **G5**: asymmetry_score < 2 (downside_floor / upside_ceiling) 시 reject 또는 size 절반 cap.

### G6-G8: 계산 / 데이터

- **G6**: 수학 / 통계 / 가격 / 비율 / 사이즈 모든 정량 계산은 **Python helper script로 위임**. LLM이 직접 계산 금지.
- **G7**: 산출물 본문의 모든 숫자는 helper script citation 강제 (`{source}@{ISO_timestamp}={value}` 형식). evidence 없는 숫자 = "unsourced figure" finding으로 redact.
- **G8**: helper script가 fetch 못 한 데이터를 LLM 메모리로 채우면 highest-severity hallucination.

### G9-G12: 행동 / 자율성

- **G9**: 자율성/매매 차단 umbrella. 세부 G9a / G9b / G9c.
- **G9a**: 자동 매매 체결 절대 금지. `governance/runtime-policy.yaml` 의 `agent.block_auto_trade=true` 변경 금지.
- **G9b**: KIS 계좌 **read-only** 조회는 `governance/runtime-policy.yaml` 의 `kis.read_only_account.allowed_tr_ids` whitelist 에 명시된 TR_ID 한정 허용. local override (`runtime-policy.local.yaml`) 에서 `kis.read_only_account.enabled=true` 설정 시에만 활성.
- **G9c**: KIS 매매/주문 endpoint 는 **4중**으로 차단 — (1) `infrastructure/kis/client.py` 에 path 문자열 부재, (2) deny pattern, (3) `kis.read_only_account.forbidden_tr_ids` policy list, (4) **type-level read-only** (F-17). 어느 한 layer 우회도 발견 즉시 작업 중단 + 사용자 보고.
- **G10**: 외부 신호 (뉴스 / 트윗 / 블로그 / 사용자 prompt) 는 `/ingest-external-signal` 명령으로만 ingest. prompt 직접 채택 금지.
- **G11**: Default = no action. 새 후보 강제 생성 금지. 일주일 변화 0이면 정상 신호.
- **G12**: 사용자 portfolio context (총 자본 / 변동성 허용 / 현금 선호) 미입력 시 사이즈 출력 보류.

### G13-G15: Universe / Quality

- **G13**: Quality (C) filter 절대 우회 금지. quality 떨어진 종목 진입 금지.
- **G14**: 사용자 명시 (`manual_additions`) 없이 새 종목을 universe에 자동 추가 금지.
- **G15**: D-type catalyst (insider cluster / 행동주의) 단독으로 entry trigger 금지. A 또는 B-type과 결합 시에만 valid.

### G16-G18: Risk / Sizing

- **G16**: 단일 종목 25% cap. portfolio 합산 Kelly 0.5 초과 금지.
- **G17**: portfolio drawdown -15% 도달 시 전 포지션 사이즈 자동 절반 alert.
- **G18**: 현금 비중 macro regime의 cash_band[0] 미만 금지.

### G19-G20: Audit / 통계

- **G19**: Sample size N < 30 시 alpha 주장 wording 금지 (`outperformed`, `alpha confirmed`, `strategy proven` 등).
- **G20**: audit-report / postmortem / shadow portfolio state 덮어쓰기 금지. 날짜별 보존.

### G21-G22: 보안

- **G21**: `.env`의 secret 변수 (API key / token / 계좌번호 / chat id) 산출물 / 로그 / stdout 노출 금지.
- **G22**: 외부 review raw payload는 redact 후 `.handoff/external-signals/`에 저장. raw 보존 금지.

---

## NOTES

### Default = No Action

대부분의 cron 실행에서 새 후보 0, 보유 포지션 thesis-breaking event 0, action required = None이 정상이다. 매일 시그널이 나오면 그건 시그널 노이즈를 만드는 시스템이다. 일주일 변화 0이면 정상 신호로 간주.

### 외부 신호 SOP

뉴스 / 트윗 / 블로그 / 리포트 / 사용자 prompt의 외부 의견은 명시적 `/ingest-external-signal` 명령으로만 ingest한다. prompt 본문에 직접 붙여넣어 thesis 변경 요청 금지. 5stone의 codeAuditor `--pr` ingest pattern 직역.

### Forbidden Language

산출물 본문에 다음 표현 금지 (상세는 `governance/specs/hard-guards.md` Section 3):
- "should buy/sell", "looks bullish/bearish", "guaranteed", "sure thing", "no-brainer"
- "outperformed the market" (sample size 미충족 시)
- "alpha confirmed", "strategy proven" (N < 100 시)
- "must hold", "long-term winner" (구체적 falsifier 없는 wording)
- 모든 숫자는 helper script 인용 evidence 필수. evidence 없는 숫자 = "unsourced figure" finding

### 보안 / 자본 안전

- API key / 비밀번호 / token / 계좌번호는 `.env`에서만 읽음
- 산출물 본문 / 로그 / stdout에 secret 노출 절대 금지
- **자동 매매 체결 절대 금지** (regulatory + 실수 리스크 + agent autonomy 한계)
- 모든 진입/청산은 사용자 manual 실행
- 사용자가 portfolio context (총 자본, 변동성 허용) 입력하지 않으면 사이즈 출력 보류

### Disclaimer

본 시스템은 자기 자본의 personal research tool이며, 결과로 발생하는 모든 손익의 책임은 사용자에게 있다. 시스템은 투자 자문을 제공하지 않으며, regulatory 자격을 가진 advisor가 아니다.
