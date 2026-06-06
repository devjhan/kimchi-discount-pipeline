# Cloud Routine Prompt — Investment Daily Brief

> ⚠️ **[DEPRECATED 2026-05-13] — 본 절차는 비활성이다.**
> cloud routine 경로는 KIS/DART/KRX API 의 cloud provider IP 차단으로 무력화됐다
> (`applications/cloud_routine_run.sh` 는 즉시 `exit 1`). **자동 스케줄의 canonical
> 경로는 로컬 launchd** (`infrastructure/scheduling/install.sh` 단일 통로) 이며,
> `/schedule` (cloud) · scheduled-tasks 경로는 사용하지 않는다.
> 본 문서는 IP 정책 변경 시 재활성 reference 로만 보존 — 리팩토링 sweep 제외.
> 근거: `governance/specs/deployment-residency.md`.

> 본 파일은 Anthropic-managed Claude Code Routines (https://claude.ai/code/routines)
> 의 routine prompt 본문 template 이다. routine 생성 시 본 파일 §"Prompt Body"
> 의 내용을 그대로 paste 하거나, `/schedule update` 로 routine prompt 를 갱신할
> 때 본 텍스트를 인용한다.
>
> repo 안에 commit 하는 이유: routine prompt 가 cloud 전용 UI 안에서만 존재하면
> diff / 코드 review 가 불가능. 본 markdown 으로 SSoT 유지하고, cloud 의 prompt
> 는 본 파일의 single source 를 mirror.

---

## 1. Manual setup precondition (사용자 1회)

| # | 항목 | 위치 | 비고 |
|---|---|---|---|
| M1 | Slack connector 연결 | claude.ai 의 routine 작성 form | 채널 ID 결정 |
| M2 | Gmail connector 연결 | 동일 | 수신/발신 주소 결정 |
| M3 | Cloud environment 환경변수 등록 | Environment 탭 | 본 §3 의 env list 모두 |
| M4 | Network access = Custom | Environment 탭 | `query1.finance.yahoo.com`, `opendart.fss.or.kr`, `openapi.koreainvestment.com`, `api.stlouisfed.org`, `en.wikipedia.org`, `data.krx.co.kr`, `open.krx.co.kr` (KRX 휴장일 refresh-gate 자동 호출) |
| M5 | Routine 생성 + schedule 지정 | claude.ai routine UI 또는 `/schedule daily investment-brief at 7:30am KST` | 권장: 평일 KST 07:30 (장 시작 전). daily routine 외 weekly/quarterly audit routine 은 §6 참조 |
| M6 | Allow unrestricted branch pushes = OFF | Permissions 탭 | brief commit 은 `claude/` prefix branch 만 |

## 2. Repository

`devjhan/k-investment-advisor-project` (default branch: `main`)

## 3. Required cloud env vars

### 3.1 기본 (slack + gmail 채널 사용 시)

| 변수 | 용도 | secret? |
|---|---|---|
| `KIS_APP_KEY` | KIS API auth | ✅ |
| `KIS_APP_SECRET` | KIS API auth | ✅ |
| `KIS_ACCOUNT_NUMBER` | positions_sync (`12345678-01` 형식) | ✅ |
| `DART_API_KEY` | DART filings | ✅ |
| `FRED_API_KEY` | FRED macro indicators | ✅ |
| `NOTIFY_CHANNELS` | dispatcher 활성 채널 CSV — `slack` / `gmail` / `slack,gmail` 등. default `slack` | — |
| `NOTIFY_SLACK_CHANNEL` | Slack adapter 발송 채널 ID (예: `C0123456`) | — |
| `NOTIFY_EMAIL_TO` | Gmail adapter 수신 주소 | — |
| `NOTIFY_EMAIL_FROM` | Gmail adapter 발신 주소 (Gmail 연결 계정과 일치) | — |

### 3.2 옵셔널 — 다른 notifier 채널 활성화 시

`NOTIFY_CHANNELS` 에 추가하는 채널에 한해 다음 env 도 set. 채널별 adapter 가
`required_env` 미설정 시 status=`skipped` (graceful).

| 채널 | 추가 env | secret? |
|---|---|---|
| `telegram` | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | ✅ |
| `discord` | `NOTIFY_DISCORD_WEBHOOK_URL` | ✅ |
| `kakao` | `NOTIFY_KAKAO_ACCESS_TOKEN` | ✅ |
| `webhook` | `NOTIFY_WEBHOOK_URL`, `NOTIFY_WEBHOOK_AUTH` (옵셔널) | webhook URL: 환경에 따라 |

### 3.3 Gitignore yaml 의 cloud env fallback (필수 / 옵셔널)

`$RUNTIME_POLICY_LOCAL_PATH`, `$USER_PORTFOLIO_PATH`, `$USER_BEHAVIOR_PATH`
는 모두 **gitignore** 이므로 cloud session worktree 에 존재하지 않는다.
helper 들은 file 우선 + env fallback hybrid 로 read 한다 — env 가 set 이면
file 부재 시 그 값을 채택한다 (infrastructure._common.utils 의 load_*
함수들).

#### 3.3.1 runtime-policy override (필수 — 미설정 시 Stage 5 보류 + KIS skip)

| 변수 | 매핑 | 권장값 | secret? |
|---|---|---|---|
| `RUNTIME_POLICY_USER_ACK_NOT_FINANCIAL_ADVICE` | `user_acknowledged.not_financial_advice` | `true` | — |
| `RUNTIME_POLICY_USER_ACK_NO_AUTO_TRADE` | `user_acknowledged.no_auto_trade` | `true` | — |
| `RUNTIME_POLICY_USER_ACK_SAMPLE_SIZE_LIMITS` | `user_acknowledged.sample_size_limits` | `true` | — |
| `RUNTIME_POLICY_KIS_READ_ONLY_ENABLED` | `kis.read_only_account.enabled` | `true` (KIS 계좌 조회 활성) | — |

bool 값은 `true`/`1`/`yes`/`on` 또는 `false`/`0`/`no`/`off` (대소문자 무관).

#### 3.3.2 user portfolio (Stage 5 사이즈 권고 활성화)

| 변수 | 매핑 | 형식 | secret? |
|---|---|---|---|
| `USER_PORTFOLIO_TOTAL_KRW` | `portfolio.yaml.total_capital_krw` | 정수 (원) — 예: `2000000` | — |
| `USER_PORTFOLIO_DRAWDOWN_PCT` | `portfolio.yaml.current_drawdown_pct` | float 0.0~1.0 — 예: `0.08` (8%) | — |
| `USER_PORTFOLIO_CASH_PCT` | `portfolio.yaml.current_cash_pct` | float 0.0~1.0 — 예: `0.45` (45%) | — |

`USER_PORTFOLIO_TOTAL_KRW` 미설정 시 Stage 5 가 G12 `no_user_portfolio` 로
사이즈 권고 보류 (Stage 0~4 는 정상 진행).

#### 3.3.3 user behavior (옵셔널)

| 변수 | 매핑 | 형식 | secret? |
|---|---|---|---|
| `USER_BEHAVIOR_YAHOO_FALLBACK_ENABLED` | `behavior.yaml.yahoo_fallback.enabled` | bool | — |

KIS API 미가용 시 Yahoo 로 자동 fallback 할지 여부.  cloud network policy
가 KIS 도메인 차단된 경우만 의미 — default `false` (한국 종목 데이터 quality
이슈로 보수적).

**Cloud 권장**: `USER_BEHAVIOR_YAHOO_FALLBACK_ENABLED=true` set 권장. KIS
`/oauth2/tokenP` 가 cloud 네트워크에서 timeout 빈도 높음 (2026-05-12 cron 에서
pref-spread 5쌍 전부 가격 unavailable 사고). client 측 retry (`infrastructure
/kis/client.py` 의 `_post_json(retry=2)`) 로 transient timeout 은 흡수되지만,
KIS 도메인 자체가 cloud IP 에서 차단되는 경우는 Yahoo path 만 작동. Yahoo 는
KRX 종목을 `{6-digit}.KS` / `.KQ` suffix 로 fetch — 보조 fallback 한정 (실제
체결가 quality 검증 미필이므로 사이즈 결정에는 KIS 가 우선).

---

## 4. Prompt Body (cloud routine 본문에 paste)

```
You are the investment_v2 daily routine.

The SessionStart hook chain ($HOOKS_DIR/resolve_aliases.sh → $HOOKS_DIR/inject_session_state.sh) has already exported $TRAIL_TODAY as an absolute path containing today's KST date — weekend-normalized to the previous trading day. $TRAIL_TODAY now points at operations/<DATE>/ directly (the .trails/ sub-directory was removed on 2026-05-12). Derive <DATE> from it:

     <DATE> = $(basename "$TRAIL_TODAY")

Do NOT recompute via `TZ=Asia/Seoul date +%Y-%m-%d`. On weekends that gives raw today, which differs from $TRAIL_TODAY's normalized trading day — using raw today would push an empty operations/<raw_weekend>/ directory for that weekend.

Execute these steps in order. If any step fails, log the failure and continue (graceful degrade) — but never invent missing data.

The helpers read runtime-policy / portfolio / behavior from gitignored yaml files first, falling back to cloud env vars (see §3.3) when those files are absent — so NO `Write` step is needed at the start of the routine. If the cloud env is missing a required key, the corresponding gate degrades gracefully (Stage 5 produces blocked_reason instead of size; positions_sync returns skipped; etc.).

1. Run the deterministic pre-Stage4 pipeline (Stage 0~3 + positions_sync + portfolio_state_derive). This produces inputs for Stage 4 LLM skill but does NOT yet compute sizing:
     bash $OPERATIONS_DIR/cron/cloud_routine_run.sh

2. Invoke Stage 4 thesis auditor (LLM skill — runs in this same session). Produces $TRAIL_TODAY/04-thesis-candidates.json:
     /investment-stage4-thesis-auditor <DATE>

2.5. Run the post-Stage4 helpers (Stage 5 sizing + 5b falsifier-proximity + 5c event-falsifier-linker + 5d thesis-expiry). These read 04-thesis-candidates.json from Step 2:
     bash $OPERATIONS_DIR/cron/daily_pipeline.sh --date <DATE> --phase post-stage4

3. Invoke Stage 6 brief author (LLM skill — runs in this same session):
     /investment-stage6-brief-author <DATE>

3.5. Thesis expiry summary (Stage 5d 산출 surface):
     Read tool: $TRAIL_TODAY/05d-thesis-expiry.json
     - stats.by_tier.expired > 0 OR stats.by_tier.overdue > 0 인 경우:
       brief markdown 첫 줄에 "[THESIS EXPIRY ALERT] expired=N overdue=M" prepend.
     - stats.by_tier.warn > 0 (T-30 임박) 인 경우:
       brief 본문 "## Positions" 섹션에 marker 추가 (새 fact 없이 expiry-{date}.md
       파일들의 expiry_date / days_remaining 만 인용).
     - records 의 needs_user_decision=true 인 ticker 목록은 final summary 에 포함.

4. Read brief markdown:
     Read tool: $DAILY_BRIEF_PATH         (= operations/<DATE>/daily-brief.md, date-dir root — NOT under .trails/)

5. Run notification dispatcher to build per-channel payloads (no external send yet).
   Brief lives at $DAILY_BRIEF_PATH (operations/<DATE>/daily-brief.md, the date-dir root); dispatcher's result JSON goes into the .trails/ sub-dir alongside the other stage intermediates:
     python -m infrastructure.notify.dispatcher --brief "$DAILY_BRIEF_PATH" --out-json "$TRAIL_TODAY/_notify-results.json"

   Then read $TRAIL_TODAY/_notify-results.json.

   AdapterResult.status semantics ($BRIEF_AUTHOR_DIR/notifiers/_base.py:57-65):
     - 'sent'    = boundary 검증 통과 + payload ready. 본 routine 이 payload 를 받아 MCP tool 로 실제 송신해야 함 (dispatcher 자체는 송신하지 않음).
     - 'skipped' = required_env 미설정 또는 dry-run.
     - 'blocked' = G19 forbidden wording / G21 secret leak 검사 실패. 절대 송신 금지.
     - 'error'   = 외부 송신 / HTTP 오류 (webhook 같은 직접-송신 채널에서만 발생 가능).

   For each channel whose status == "sent" AND payload != null:
     - slack:  call slack_send_message MCP tool with channel=payload['channel'] and text=payload['text']
     - gmail:  call create_draft MCP tool with to=payload['to'], from=payload['from'], subject=payload['subject'], body=payload['body']
     - other channels with payload['_mcp_tool_hint']: dispatch via the hinted MCP tool.
     - channels lacking an MCP route: skip (webhook adapter already sends in-process via stdlib HTTP).

   For status == "blocked": DO NOT send. Surface the BriefBlocked reason in the final summary.
   For status == "error":   report the error string; do not retry within this fire.

6. Commit and push the day's full artifact set (cloud routine is now a SoT — see .gitignore comment for the 2026-05-12 policy change):
     git checkout -b claude/brief-<DATE>
     git add "$DATE_TODAY_DIR/" "$AUDIT_DIR/" "$POSITIONS_DIR/" "$EXTERNAL_SIGNALS_DIR/"
     git commit -m "Daily artifacts — <DATE>"
     git push origin HEAD

   $DATE_TODAY_DIR points at operations/<DATE>/, which contains both the brief and the .trails/ sub-dir — a single add covers brief + stage JSON + dispatcher result.

   (.gitignore still blocks .env / runtime-policy.local.yaml / portfolio.yaml / behavior.yaml / breadth.yaml — those secret/user-env files stay local.)

7. Final 1-line summary: stage status (pipeline OK/FAIL counts), thesis expiry tier 분포 (notice/warn/expired/overdue), notify status per channel (sent/skipped/blocked/error), branch push result.

Hard rules:
  - Never print secret values to the transcript (KIS_APP_KEY/SECRET, KIS_ACCOUNT_NUMBER, FRED_API_KEY, DART_API_KEY, TELEGRAM_BOT_TOKEN, NOTIFY_*_TOKEN).
  - Never call any KIS write/order endpoint. KisAutoTradeBlocked exception means: stop, report, do not retry.
  - Never modify pipeline JSON outputs (00-*, 01-*, 02-*, 03-*, 04-*, 05-*) by hand.
  - Never push to main. Only claude/-prefixed branches are allowed.
```

---

## 5. Slot for one-off / ad-hoc runs

`/schedule run <routine-id>` 로 routine 즉시 실행. 본 prompt 는 daily 간격을
가정하지만, 같은 prompt 를 one-off 로도 실행 가능 (one-off 는 daily routine cap
미차감).

---

## 6. Schedule 권장값

### 6.1 Daily brief routine (본 prompt body)

| 옵션 | 시점 | 비고 |
|---|---|---|
| 평일 KST 07:30 (권장) | 장 시작 1.5시간 전 | brief 도착 후 사용자가 09:00 장 시작 전 검토 가능 |
| 평일 KST 18:00       | 장 마감 1.5시간 후 | 종가 기준 사용자 review (다음날 prep) |
| 매일 KST 06:00       | 휴장일 포함        | helper 의 `normalize_to_trading_day` 가 직전 거래일로 date 정규화 — 휴장일에도 변화 0 brief 산출. Default = no action 정책과 정합 |

routine 생성 시 시간은 사용자 본인 zone 기준 입력 → cloud 가 UTC 변환 + 일정
stagger (수 분 지연 가능).

### 6.2 Weekly process audit routine (별도 등록 권장)

본 prompt body 와 별개로 두 번째 routine 을 만들어 일주일 단위 process 위반
집계 (vague falsifier accepted, A 단독 claim no evidence, secret leak, 사이즈
cap 위반 등) 를 수행한다.

- Schedule: 일요일 KST 22:00 또는 월요일 KST 06:00
- Prompt body 핵심:
  ```
  /investment-audit-process <THIS_WEEK_YYYY-WW>
  ```
  뒤이어 본 daily prompt body 의 Step 5~6 (notify dispatch + git push) 동일 적용.
- 산출: `$AUDIT_DIR/process-{YYYY-WW}.md`

### 6.3 Quarterly outcome audit routine (별도 등록 권장)

LLM filter (tier_2) vs Mechanical (tier_1) 4-tier shadow portfolio 분기 수익률
비교. 4 분기 연속 tier_2 < tier_1 시 self-disable trigger 발동.

- Schedule: 매 분기 첫 평일 KST 07:00 (예: 1/2, 4/1, 7/1, 10/1 직후 평일)
- Prompt body 핵심:
  ```
  /investment-audit-outcome <PREV_QUARTER_YYYY-Q>
  ```
- 산출: `$AUDIT_DIR/outcome-{YYYY-Q}.md`, `$AUDIT_DIR/disable-trigger.json`
- **전제 조건**: `python -m domains.audit_integrity.main` (결정론 엔진, F-6) 이 daily
  routine 안에서 실행되어 `$AUDIT_DIR/shadow-portfolio-state.json` 이 일별 갱신/bootstrap
  되어 있어야 비교 가능.
