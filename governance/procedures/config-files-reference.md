# Config Files Reference

> 본 문서는 사용자 / agent 가 환경 / 정책 / 사용자 context 변수를 어느
> 파일에서 찾고 / 갱신할지 빠르게 알기 위한 매핑 reference. 변수명 자체의
> rationale (G-rule 정합 / 의존 helper) 도 함께 정리한다.

`.env` 의 secret 값은 산출물 / stdout / 로그에 절대 노출 금지 (G21).
agent toolchain 은 `.env*` 파일 직접 접근 차단 (env-guard hook); 단
`.example` / `.template` suffix template 은 허용.

---

## 1. 5개 config 파일 (DDD bounded context 별)

| 파일 | layer | 용도 | git | 변경 빈도 |
|---|---|---|---|---|
| `.env` | infrastructure | API key / token (secret) | ignore (`.example` 추적) | 가입 시 1회 |
| `governance/runtime-policy.yaml` | governance | hard policy default (G9 정적 enforcement) | 추적 | 매우 낮음 |
| `governance/runtime-policy.local.yaml` | governance | 사용자 USER_ACKNOWLEDGED override | ignore (`.example` 추적) | 첫 활성화 시 |
| `config/user/portfolio.yaml` | config | 사용자 자본 / drawdown / cash | ignore (`.example` 추적) | 분기 / 자본 변경 시 |
| `config/user/behavior.yaml` | config | runtime 행동 switch (Yahoo fallback 등) | ignore (`.example` 추적) | 환경 결정 시 1회 |
| `config/user/manual_additions.yaml` | config | 사용자 명시 universe 추가 종목 (G14) | ignore (`.example` 추적) | 후보 추가 시 (ADR-0015) |
| `config/user/exclusions.yaml` | config | 사용자 명시 universe 제외 ticker | ignore (`.example` 추적) | 제외 결정 시 (ADR-0015) |
| `config/signals/macro/breadth.yaml` | config | S&P breadth manual input | ignore (`.example` 추적) | 주 1회 권장 갱신 |

`thresholds.yaml` 은 정량 임계값 SSoT 로 별도. 경로는 `infrastructure/_common/utils.py`
의 path helper 가 직접 계산한다 (중앙 topology alias SSoT 는 제거됨). 본 표는 사용자
환경 설정 파일만 다룸.

> **signals 분리 주의**: `config/signals/` 에는 *사용자 입력* breadth(`macro/breadth.yaml`,
> 재생성 가능)만 거주한다. `/ingest-external-signal` 의 per-ticker 산출(agent 생성 ·
> append-only 증거)은 `config/` 가 아니라 `telemetry/external_signals/{ticker}/` 로 분리됐다
> (ADR-0008 분류축: 재생성 가능성+수명+소유 — audit/nav-history/policy_drafts 와 동류).
> helper 도 `external_signals_dir()`(breadth) / `external_signal_intake_dir()`(ingest) 로 분리.

---

## 2. 변수 → 파일 / 위치 매핑

### `.env` (secret only)

| 변수 | 의존 stage / helper | 비고 |
|---|---|---|
| `DART_API_KEY`   | Stage 1 / 2a / 3 / 3a / 3b | 발급: opendart.fss.or.kr |
| `KIS_APP_KEY`    | Stage 1b / 1c / 3b / positions_sync | 시세 read-only + 계좌 read-only (whitelist) |
| `KIS_APP_SECRET` | 위와 pair                  | |
| `KIS_ACCOUNT_NUMBER` | positions_sync (G9b)    | `12345678-01` 형식 (CANO 8자리-ACNT_PRDT_CD 2자리). 미설정 시 positions_sync graceful skip. KIS read-only account 활성화 (`runtime-policy.local.yaml` 의 `kis.read_only_account.enabled=true`) 시에만 호출됨 |
| `FRED_API_KEY`   | Stage 0                   | 발급: fred.stlouisfed.org |
| `TELEGRAM_BOT_TOKEN` | (옵셔널)              | manual notify 만 |
| `TELEGRAM_CHAT_ID`   | (옵셔널)              | 위와 pair |
| `NOTIFY_CHANNELS` | brief notify dispatcher | CSV — `slack,gmail` 형식 |
| `NOTIFY_SLACK_CHANNEL` | Slack adapter | 발송 채널 ID |
| `NOTIFY_EMAIL_TO` / `NOTIFY_EMAIL_FROM` | Gmail adapter | 수신 / 발신 주소 |
| `DEEPSEEK_API_KEY` | llm dispatcher (Stage 4/6, ADR-0016) | Claude Code DeepSeek 백엔드 auth — adapter 가 `ANTHROPIC_AUTH_TOKEN` 으로 주입(`ANTHROPIC_API_KEY` 제거 → Anthropic $0). 발급: platform.deepseek.com |
| `EMBEDDING_API_KEY` | segment 벡터 인덱스 (`segment_index_main`) | semantic 세그먼트 멤버십 전용. 부재 시 semantic leaf UNKNOWN(비매칭) graceful (ADR-0012). 발급: platform.openai.com |
| `EMBEDDING_BASE_URL` | 위와 함께 (옵셔널) | 기본 `https://api.openai.com/v1`. OpenAI-호환 게이트웨이 시 override |
| `EMBEDDING_MODEL` | 위와 함께 (옵셔널) | 기본 `text-embedding-3-small` (OpenAI 계통) |

`KIS_ACCOUNT_NUMBER` 는 G9b read-only 정책 활성 시 6종 endpoint
(주식잔고조회 / 실현손익 / 일별체결 / 매수가능 / 매도가능수량 / 계좌자산) 호출에
사용된다. 매매/주문 endpoint 는 코드 부재 + Bash deny + policy whitelist 의 3중
차단으로 절대 호출되지 않는다 (G9a/G9c).

`EMBEDDING_*` 는 segment-scoped profile 의 **semantic 분류**(concept anchor cosine)에만
쓰인다 (ADR-0012). 벡터 인덱스는 `python -m domains.universe.segment_index_main` 가
`telemetry/segments/vectors.sqlite` 에 적재한다. 벡터 가속은 `pip install -e '.[semantic]'`
(sqlite-vec) — 미설치 시 stdlib `sqlite3` + brute-force cosine 로 정확 degrade (KR 특수상황
규모 충분). 키 부재/오프라인 시 semantic leaf 는 UNKNOWN(비매칭) graceful, rule-based
선택 속성(scalar)은 계속 동작. 회사 공개 공시 텍스트가 제3자 임베딩 API 로 전송됨
(ADR-0012 10-a 사용자 결정) — 키 값 노출 금지 (G21).

### `governance/runtime-policy.yaml` + `.local.yaml`

base 와 .local 은 deep-merge 되며 .local 값이 우선 (사용자 override).

| 키 path | 기본값 | 의미 | 변경 책임 |
|---|---|---|---|
| `agent.block_auto_trade` | `true` | G9a 정적 enforcement — 변경 금지 | (변경 불가) |
| `user_acknowledged.not_financial_advice` | `false` | 자문 아님 인지 (G19 cross-cutting) | `.local.yaml` 에서 사용자 |
| `user_acknowledged.no_auto_trade`        | `false` | 자동 매매 금지 (G9) 인지 | `.local.yaml` 에서 사용자 |
| `user_acknowledged.sample_size_limits`   | `false` | sample size 제약 (G19) 인지 | `.local.yaml` 에서 사용자 |
| `kis.read_only_account.enabled`          | `false` | G9b — KIS 계좌 read-only 호출 활성. 본값을 `.local.yaml` 에서 `true` 로 override 해야 positions_sync helper 동작 | `.local.yaml` 에서 사용자 |
| `kis.read_only_account.allowed_tr_ids`   | (base 7개)  | whitelist — base 그대로 사용. 임의 변경 금지 (KIS API 변경 시 governance issue) | (변경 불가) |
| `kis.read_only_account.forbidden_tr_ids` | (base 5개)  | 매매/주문 TR_ID 명시 거부 list. 본 list 호출 시 `KisAutoTradeBlocked` raise (audit 신호) | (변경 불가) |

3 ack flag 모두 true 일 때만 `daily_pipeline.sh` USER_ACK gate 통과
(`infrastructure._common.utils.all_user_acknowledged()`).

### `config/user/portfolio.yaml`

Stage 5 sizing helper (`sizing.py`) 의 G12 boundary 결정.

| 키 | 형식 | 비고 |
|---|---|---|
| `total_capital_krw` | int / null | 총 자본 (원). null 시 사이즈 권고 보류 (G12). **manual 입력 필수**. |
| `current_drawdown_pct` | float / null | [deprecated — derived] `portfolio_state_derive` 가 자동 산출. null 유지 권장. 명시값은 derived 보다 우선. |
| `current_cash_pct` | float / null | [deprecated — derived] `portfolio_state_derive` 가 자동 산출. null 유지 권장. |
| `volatility_tolerance` | enum / null | low / medium / high. 1차 helper 미참조 (예약). |

`current_drawdown_pct` / `current_cash_pct` 자동화 우선순위 (`sizing.py`):
1. portfolio.yaml 명시값 (사용자 override)
2. `$POSITIONS_DIR/_account/derived-{date}.json` (`portfolio_state_derive` 산출)
3. 0 fallback (둘 다 미가용)

### `config/user/behavior.yaml`

| 키 path | 형식 | 의미 |
|---|---|---|
| `yahoo_fallback.enabled` | bool | Yahoo public chart endpoint fallback 자동 활성. CLI `--allow-yahoo-fallback` 명시 시 본 값보다 우선. |

### `config/signals/macro/breadth.yaml`

| 키 | 형식 | 의미 |
|---|---|---|
| `spx_above_200dma_pct` | float / null | 0.0 ~ 1.0. null 시 Stage 0 breadth indicator skip. |
| `observed_at` | str / null | ISO date. citation 신선도 audit. |
| `source` | str / null | 자유 string (예: "yardeni.com 2026-05-09"). |

---

## 3. Helper × 파일 의존 매트릭스

| Helper | runtime-policy | portfolio.yaml | behavior.yaml | breadth.yaml | DART_API_KEY | KIS_* | FRED_API_KEY |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| Stage 0 macro_regime               | — | — | — | ✓ | — | — | ✓ |
| Stage 1 universe                   | — | — | — | — | ✓ | — | — |
| Stage 1b nav_calc                  | — | — | ✓ | — | — | ✓ | — |
| Stage 1c pref_spread               | — | — | ✓ | — | — | ✓ | — |
| Stage 2a fin_fetch                 | — | — | — | — | ✓ | — | — |
| Stage 2 quality_filter             | — | — | — | — | — | — | — |
| Stage 3a index_deletion            | — | — | — | — | ✓ | — | — |
| Stage 3b earnings_panic            | — | — | ✓ | — | ✓ | ✓ | — |
| Stage 3 catalyst_scan              | — | — | — | — | ✓ | — | — |
| Stage 5 sizing                     | — | ✓ | — | — | — | — | — |
| Stage 5d thesis_expiry_monitor     | — | — | — | — | — | — | — |
| positions_sync                     | ✓ | — | — | — | — | ✓ | — |
| portfolio_state_derive             | — | — | — | — | — | — | — |
| breadth_fetch (Stage 0a)           | — | — | — | — | — | — | — |
| ingest-external-signal (skill)     | — | — | — | — | — | — | — |
| segment_index_main (벡터 build)    | — | — | — | — | ✓¹ | — | — |
| `daily_pipeline.sh` USER_ACK gate  | ✓ | — | — | — | — | — | — |

`USER_ACK gate` 가 fail (3 flag 어느 하나 false) 면 helper 자체는 모두
실행되지만 사이즈 권고 보류 + warning 노출. 첫 활성화는 사용자가
`runtime-policy.local.yaml` 작성 후 3 flag true 변경.

¹ `segment_index_main` 의 `DART_API_KEY` 는 `DartTickerTextSource`(사업의 내용 본문)
용이며 `--texts-file` 수기 큐레이션으로 대체 가능. 추가로 semantic 벡터화에는
`EMBEDDING_API_KEY`(위 `.env` 표) 가 필요하다 — 부재 시 scalar 만 적재하고 semantic
멤버십은 UNKNOWN 으로 graceful degrade.

---

## 4. 첫 사용자 setup 절차

```sh
# 1. Secret (API keys)
cp .env.example .env
# .env 안에 DART_API_KEY / KIS_APP_KEY / KIS_APP_SECRET / FRED_API_KEY 입력

# 2. Activation flags
cp governance/runtime-policy.local.yaml.example governance/runtime-policy.local.yaml
# .local.yaml 안의 user_acknowledged.* 3 flag 모두 true 로 변경

# 3. Portfolio context (사이즈 권고 활성화)
cp config/user/portfolio.yaml.example config/user/portfolio.yaml
# total_capital_krw 입력 (예: 100000000 = 1억원)

# 4. (옵셔널) Yahoo fallback / breadth manual
cp config/user/behavior.yaml.example config/user/behavior.yaml
cp config/signals/macro/breadth.yaml.example config/signals/macro/breadth.yaml

# 5. Pipeline 실행
bash applications/daily_pipeline.sh --date $(date +%Y-%m-%d)
```

---

## 5. .gitignore 매핑

다음 4 파일은 `.gitignore` 처리됨 (사용자별 데이터 / secret 보호):

```
.env
governance/runtime-policy.local.yaml
config/user/portfolio.yaml
config/user/behavior.yaml
config/signals/macro/breadth.yaml
```

`.example` 변형은 모두 git 추적 (template 제공 목적).
