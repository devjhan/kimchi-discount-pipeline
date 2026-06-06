# Shared Bootstrap Contract — Investment Pipeline

본 문서는 investment 파이프라인의 모든 agent / skill이 공유하는 bootstrap 규약이다. 5stone (`~/.claude/skills/_shared/5stone/bootstrap.md`)과 동일한 single-source 패턴을 따르며, investment 도메인 고유 룰을 정의한다.

각 skill은 본문에서 본 문서를 명시적으로 참조한다. 본 문서가 없거나 읽을 수 없으면 인용 skill은 즉시 ERROR로 중단한다.

---

## Section 1. Source of Truth Hierarchy (ABSOLUTE PRIORITY)

각 skill은 자체 역할별 지시를 적용하기 전에, 반드시 아래 순서로 읽고 준수한다.

1. 사용자 명시적 결정
2. 프로젝트 루트 `CLAUDE.md`
3. `$AXIOMS_DIR/**/*.md`
4. `$SPECS_DIR/**/*.md` (있으면)
5. `$THRESHOLDS_PATH` (정량 임계값)
6. `.env` (runtime config 변수, secret 외에는 자유 인용)
7. 현재 skill 문서
8. `$TRAIL_TODAY/*` 및 `$POSITIONS_DIR/{ticker}/*`
9. helper script raw output

### Hard Rules

- `CLAUDE.md` / `$AXIOMS_DIR/**` / `$SPECS_DIR/**` / `$THRESHOLDS_PATH`은 현재 skill 문서보다 우선한다.
- 현재 skill 문서는 상위 문서를 override / narrow / reinterpret할 수 없다.
- 상위 문서와 현재 skill 문서가 충돌하면, 상위 문서를 따르고 충돌 사실을 stdout에 1줄 이상 명시한다.
- 필요한 상위 문서가 없거나 읽을 수 없으면 추정하지 말고 즉시 보고한다.
- `.env`의 secret 변수 (`DART_API_KEY`, `KIS_APP_SECRET`, `KIS_ACCOUNT_NUMBER`, `TELEGRAM_BOT_TOKEN` 등)는 산출물 본문 / 로그 / stdout에 절대 노출 안 함.
- secret 변수 vs 비-secret 변수의 분류 기준: API key / token / password / 계좌번호 / chat id = secret. 그 외 path / timezone / behavior switch / cron schedule = 비-secret (인용 가능).

---

## Section 2. Date / Ticker Namespace Rules

### 날짜 형식

```
YYYY-MM-DD (KST 기준)
주말 / 공휴일 cron 실행 시: 가장 최근 거래일로 normalize
```

### Ticker 형식

```
한국: 6자리 숫자 (예: 005930, 035420)
미국: ticker symbol (예: AAPL, MSFT)
구분 prefix가 필요한 경우: KR:005930, US:AAPL
```

### 경로 표기 (alias shorthand)

본 문서·SKILL 본문의 `$TRAIL_TODAY` 등은 **shorthand 표기**다. 별도의 alias 해석
메커니즘(구 `topology.yaml` + `from_alias`)은 제거되었으며, 경로는 각 도메인 코드가
`infrastructure._common.utils` 의 path helper (`trail_dir()` / `audit_dir()` /
`positions_dir()` 등) 로 직접 계산한다. 산출물 경로가 필요하면 SessionStart 의
**"주요 경로" 블록**에 출력된 오늘 KST 기준 실제 절대경로를 사용한다.

| shorthand | 실제 경로 (repo root 기준) |
|---|---|
| `$TRAIL_TODAY` | `operations/{오늘 KST 거래일}` |
| `$AUDIT_DIR` | `telemetry/audit` |
| `$POSITIONS_DIR` | `telemetry/positions` |
| `$EXTERNAL_SIGNALS_DIR` | `config/signals` |
| `$DAILY_BRIEF_PATH` | `operations/{오늘 KST 거래일}/daily-brief.md` |
| `$THRESHOLDS_PATH` | `governance/thresholds.yaml` |
| `$AXIOMS_DIR` | `governance/AXIOMS` |
| `$SPECS_DIR` | `governance/specs` |
| `$SKILLS_SHARED_DIR` | `.claude/skills/_shared/investment` |

### 산출물 경로 매핑

| 종류 | 경로 |
|---|---|
| 일별 macro regime | `$TRAIL_TODAY/00-macro-regime.json` |
| 일별 macro regime narrative (LLM) | `$TRAIL_TODAY/00-macro-regime-narrative.md` |
| 일별 universe | `$TRAIL_TODAY/01-universe.json` |
| 일별 quality filter | `$TRAIL_TODAY/02-quality-filter.json` |
| 일별 quality lens (LLM 정성) | `$TRAIL_TODAY/02-quality-lens.json` |
| 일별 catalyst events | `$TRAIL_TODAY/03-catalyst-events.json` |
| 일별 thesis candidates | `$TRAIL_TODAY/04-thesis-candidates.json` |
| 일별 sizing | `$TRAIL_TODAY/05-sizing-recommendation.json` |
| 일별 thesis expiry status (5d) | `$TRAIL_TODAY/05d-thesis-expiry.json` |
| 일별 brief (사람용) | `$DAILY_BRIEF_PATH` |
| Position thesis (진입 시) | `$POSITIONS_DIR/{ticker}/thesis.md` |
| Position drift (일별) | `$POSITIONS_DIR/{ticker}/drift-{date}.md` |
| Position expiry (일별 5d) | `$POSITIONS_DIR/{ticker}/expiry-{date}.md` |
| Position postmortem | `$POSITIONS_DIR/{ticker}/postmortem.md` |
| Positions sync summary (KIS) | `$POSITIONS_DIR/_summary-{date}.json` |
| Portfolio derived state | `$POSITIONS_DIR/_derived-{date}.json` |
| External signal ingest | `$EXTERNAL_SIGNALS_DIR/{ticker}/{date}-{seq}.md` |
| Process audit (주간) | `$AUDIT_DIR/process-{YYYY-WW}.md` |
| Outcome audit (분기) | `$AUDIT_DIR/outcome-{YYYY-Q}.md` |
| Shadow portfolio state | `$AUDIT_DIR/shadow-portfolio-state.json` |
| Trade log (4 tier) | `$AUDIT_DIR/trade-log-{tier}.csv` |
| Self-disable trigger | `$AUDIT_DIR/disable-trigger.json` |

### Storage Hard Rules

- 모든 $OPERATIONS_DIR 산출물은 `$OPERATIONS_DIR/` 아래에만 저장.
- `$OPERATIONS_DIR` 는 `.gitignore`에 등록되어야 한다.
- broad glob (`**/$OPERATIONS_DIR/**`) 사용 금지. 항상 `$OPERATIONS_DIR/{specific-prefix}/*` 사용.
- 같은 날짜 같은 stage 산출물은 덮어쓰지 않고 `.{N}` suffix로 보존 (예: `00-macro-regime.json` 존재 시 `00-macro-regime.1.json`).

---

## Section 3. Forbidden Language (cross-cutting enforcement)

산출물 본문 / stdout / 로그에 다음 표현이 등장하면 **즉시 REMOVE 하고 evidence-based phrasing으로 대체**.

`$THRESHOLDS_PATH`의 `enforcement.forbidden_language` 섹션이 single source. 본 문서는 그 의미와 대체 패턴을 설명한다.

### Recommendation 단어 차단

| 차단 표현 | 사유 |
|---|---|
| "should buy", "should sell" | judgment 침투 |
| "looks bullish", "looks bearish" | evidence 없는 평가 |
| "guaranteed", "sure thing", "no-brainer" | uncertainty 무시 |
| "must hold" | falsifier 없는 commitment |
| "long-term winner" (구체적 falsifier 없이) | narrative |
| "undervalued" (단독) | reference 없는 valuation 주장 |
| "set to rise", "set to fall" | causal claim 없는 prediction |

### Statistical 단어 차단 (sample size 미충족 시)

| 차단 표현 | 허용 조건 |
|---|---|
| "outperformed the market" | N >= 30 + t-stat 인용 |
| "alpha confirmed" | N >= 100 + p < 0.05 |
| "strategy proven" | N >= 100 + 4분기 이상 누적 |
| "beats benchmark" | sample size + 어느 benchmark 명시 |

### 허용 phrasing 예시

```
DENY  "AAPL looks bullish, should buy"
ALLOW "AAPL Q1 EPS surprise +12% (Yahoo@2026-04-30=$2.45 vs consensus $2.18); momentum strategy score 4/5"

DENY  "Strategy outperformed the market"
ALLOW "Strategy directional signal positive, sample N=18 closed trades, t-stat=1.2, not yet conclusive (need N>=30)"

DENY  "지주사 할인 좁혀질 것"
ALLOW "OO지주 NAV 할인 65% (DART@2026-05-04). historical median 50%. catalyst: 자사주 소각 발표 (DART@2026-04-15)"
```

---

## Section 4. Required Fields per Thesis (cross-cutting enforcement)

모든 진입 thesis는 다음 5필드 강제. 누락 또는 vague 시 reject.

```
1. entry_catalyst       — 어느 event가 trigger인가 (Stage 3 catalyst event id 인용)
2. falsifier            — 다음 3 카테고리 중 1+:
                          (a) time-cap: "X months no catalyst → exit"
                          (b) metric-trigger: "metric Z reaches W → exit"
                          (c) event-trigger: "event V occurs → exit"
3. time_horizon_months  — 6 ≤ months ≤ 60 ($THRESHOLDS_PATH.thesis.time_horizon_months 기준)
4. edge_source          — A / B / C / D 중 1+ (A 인용 시 confirmation bias 추가 검증)
5. asymmetry_score      — downside_floor / upside_ceiling, 비율 < 2 시 reject 또는 size 절반 cap
```

### Vague Falsifier 패턴 (자동 reject)

`$THRESHOLDS_PATH.thesis.falsifier_vague_patterns_reject`에 등재된 패턴 + 다음 추가:

- "실적 안 좋으면", "thesis 깨지면", "전망 나빠지면"
- "if it doesn't work out", "if things change"
- 어떤 event도 명시하지 않고 "상황이 바뀌면"

### Falsifier 작성 example

```
DENY  "thesis 깨지면 exit"
ALLOW "24개월 내 NAV 할인 좁힘 catalyst (자사주 소각 / 인적분할 / 합병) 0건이면 exit (time-cap)"
ALLOW "EPS guidance 직전 분기 대비 -10% 이상 하향 시 exit (metric-trigger)"
ALLOW "행동주의 펀드 5% 신고 철회 또는 청산 시 exit (event-trigger)"
```

---

## Section 5. Hard Rules (Cross-cutting)

### A. Default = No Action

대부분의 cron run에서 새 후보 0이 정상. 매일 시그널 생성하면 false-positive 양산 시스템.

`$THRESHOLDS_PATH.enforcement.default_action.most_days_no_new_candidate: true`가 hard 보장. 매일 시그널 생성 시 false-positive 양산 alert.

### B. Numbers Must Cite Helper

산출물 본문의 모든 숫자는 helper script 인용 evidence 필수.

```
형식: {source}@{ISO_timestamp}={value}
예:   Yahoo@2026-05-03T16:00=178.50
       DART@2026-05-03={"공시번호":20260503000456,"type":"자사주_소각"}
       FRED@2026-05-03=DGS10:4.25
```

evidence 없는 숫자는 "unsourced figure" finding으로 brief에서 redact. helper script가 fetch 못 한 데이터를 LLM이 자기 메모리에서 채우면 hallucination이며, 본 시스템에서 가장 높은 severity 위반.

### C. External Signal SOP

뉴스 / 트윗 / 블로그 / 리포트 / 사용자 prompt의 외부 의견은 명시적 `/ingest-external-signal` 명령으로만 ingest. prompt 본문에 직접 붙여넣어 thesis 변경 요청 시 거부 + 표준 ingest 절차 안내.

거부 메시지 표준 형식:

```
외부 신호는 /ingest-external-signal 명령을 통해서만 thesis 변경에 영향을 준다.
다음 명령으로 먼저 ingest를 실행해 주세요:

  /ingest-external-signal {ticker} "{summary}" --source={origin} --type={analyst-note|news|twitter|...}

ingest 완료 후 다음 cron run에서 dataRecon이 fact-only로 인용한다.
즉시 thesis 변경은 수행하지 않는다.
```

### D. No Auto-Trade

자동 매매 체결 절대 금지. 모든 진입/청산은 사용자 manual 실행. agent는 추천 + monitoring + alert만.

`AGENT_BLOCK_AUTO_TRADE=true`는 변경 금지 hard config.

### E. Falsifier Daily Monitoring

보유 포지션의 falsifier proximity는 일별 cron에서 자동 검사. trigger 발동 시 즉시 alert (push notification).

monitoring 산출물: `$POSITIONS_DIR/{ticker}/drift-{date}.md`. 본문에 falsifier proximity (low / medium / high) + trigger 임박 사유.

### F. Survival Bounds

`$THRESHOLDS_PATH.sizing` 섹션이 single source:

- portfolio drawdown -15% 도달 → 전 포지션 사이즈 자동 절반 alert
- 단일 종목 25% cap
- portfolio 합산 Kelly 0.5 초과 금지
- 현금 비중 macro regime의 cash_band[0] 미만 금지

### G. Sample Size Honesty

`$THRESHOLDS_PATH.statistics.sample_gates`가 single source. 산출물 본문에 alpha 주장 wording 등장 시 N 인용 강제. N 미충족 시 forbidden language로 자동 redact.

---

## Section 6. Self-Validation (skill 호출 시 MANDATORY)

각 skill은 산출물 작성 전에 다음 자가 검증 수행:

1. CLAUDE.md / $AXIOMS_DIR / $THRESHOLDS_PATH 읽었는가?
2. 출력에 forbidden language 없는가? (recommendation + statistical 둘 다)
3. 모든 숫자에 helper citation 있는가? (`{source}@{timestamp}={value}` 형식)
4. 새 thesis라면 5필드 모두 있는가? falsifier가 vague patterns에 매치되지 않는가?
5. secret이 산출물에 노출되지 않았는가? (DART_API_KEY, KIS_APP_SECRET 등)
6. $OPERATIONS_DIR 산출물 경로가 namespace 룰을 따르는가? (Section 2 표 참조)
7. default = no action 원칙을 거역하지 않았는가? (새 후보가 강제 생성되지는 않았는가)
8. Sample size 미충족 시 forbidden statistical wording 없는가?
9. 자동 매매 / 자동 체결 / 자동 청산 시도하지 않았는가?
10. 사용자 portfolio context 미입력 시 사이즈 출력 보류했는가?

NO 하나라도 있으면 산출물 작성 중단 후 누락 보고.

---

## Section 7. Forbidden Actions (5stone 직역 + 투자 도메인 추가)

다음 행동은 어떤 skill / 어떤 cron run에서도 수행 금지:

- 자동 매매 체결
- 사용자 portfolio context 없이 사이즈 출력
- 외부 신호를 ingest 절차 없이 thesis에 반영
- helper script 호출 없이 숫자 본문에 작성
- spec / config / $AXIOMS_DIR 자동 수정
- 보유 포지션의 thesis 임의 수정 (사용자 명시 결정만)
- secret 변수의 산출물 / 로그 / stdout 노출
- 기존 audit / postmortem 덮어쓰기 (날짜별 보존)
- regulatory advice / 자문 wording 출력 ("매수 추천", "손절 권고" 등)
- 사용자 명시 없이 새 종목 universe 자동 추가 (manual_additions만)

---

## Section 8. Out of Scope (본 문서가 다루지 않는 것)

다음은 본 문서의 범위 밖이며, 각 skill 본문 또는 별도 reference에서 정의한다:

- 각 skill 고유의 input/output policy
- 각 skill 고유의 verdict enum
- 각 skill 고유의 self-check
- macro regime 정량 임계값 상세 (`$THRESHOLDS_PATH`)
- helper script schema (각 helper의 stdout JSON 명세)
- benchmark counterfactual 운영 (별도 audit skill에서 정의)
- KIS API 호출 패턴 (별도 helper script reference)
- DART 공시 분류 체계 (별도 helper script reference)

---

## Section 9. 본 Reference 문서의 우선순위 규약

- 본 문서는 모든 참조 skill의 sub-rule이다. 사용자 결정 / 프로젝트 루트 `CLAUDE.md` / `$AXIOMS_DIR/**` / `$SPECS_DIR/**` / `$THRESHOLDS_PATH` 보다 하위다.
- 본 문서가 없거나 읽을 수 없으면, 본 문서를 참조하는 skill은 즉시 ERROR로 중단한다. 추정으로 대체하지 않는다.
- 본 문서와 개별 skill 본문이 충돌하면 본 문서를 따른다. 단, skill 본문이 본 문서 항목을 **확장**하는 경우 (예: 추가 hard rule, 추가 priority) 그 확장은 본 문서의 항목과 모순되지 않는 한 그대로 유효하다.
- 모순이 의심되는 경우 본 문서의 항목을 채택하고 그 충돌 사실을 stdout 보고에 한 줄 이상 명시한다.
