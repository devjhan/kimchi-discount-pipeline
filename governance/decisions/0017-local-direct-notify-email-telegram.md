# ADR-0017 — 로컬 직접 발송 notify (email SMTP + telegram Bot API)

`status: Accepted (구현 2026-06-18)`
`date: 2026-06-18`
`refs: 0009 (claude→zed migration), 0016 (deepseek backend), G21, infrastructure/notify/, applications/run_daily_local.sh, governance/directives/30-security.md`

## Context

`infrastructure/notify/` 의 brief 발송 아키텍처는 **cloud routine(Anthropic Claude Code
Routines) MCP 위임형**으로 설계됐다. `SlackAdapter`/`GmailAdapter` 의 `send()` 는 실제
전송을 하지 않고 payload + `_mcp_tool_hint`(`slack_send_message` / `create_draft`)만
빌드해 `status="sent"` 를 반환하며, 실제 송신은 cloud routine 의 LLM 이 MCP connector 로
수행하는 구조였다.

그러나 본 저장소는 ADR-0016 이후 로컬 `run_daily_local.sh` 에서 파이프라인을 직접 구동한다.
이 로컬 경로에는 **MCP 가 없다** → notify dispatcher 가 manifest 만 남기고 아무것도 보내지
않았다. 2026-06-17 실측에서:

- **gmail**: 힌트가 `create_draft`(초안) — MCP 가 있어도 발송이 아니라 초안 생성 → 메일 미수신.
- **telegram**: deferred 스텁(`render` 가 `NotImplementedError`) → 미구현.
- **slack**: 사용자의 별도 cloud routine 으로만 수신됨(로컬 Python 은 미발송).

`adapter.py` docstring 은 이미 직접전송 경로를 명시한다: "webhook 처럼 stdlib HTTP 로 보내는
채널은 send() 안에서 직접 송신." 즉 로컬 채널은 stdlib 로 직접 보내는 것이 설계 의도와 합치한다.

## Decision

1. **`email` 채널 신규(`EmailAdapter`, 범용 SMTP, `infrastructure/notify/email.py`)**:
   stdlib `smtplib` 로 `send()` 안에서 직접 발송. `SMTP_PORT==465 → SMTP_SSL`, 그 외(기본
   587) → `STARTTLS`. `MIMEText(body, "plain", "utf-8")`. 기존 MCP-draft `gmail` 채널과
   구분하기 위해 key 를 `email` 로 둔다(Gmail 한정 아님 — 임의 SMTP).
2. **`telegram` 채널 실구현(`TelegramAdapter`)**: deferred 스텁 제거. stdlib `urllib` 로
   `https://api.telegram.org/bot<token>/sendMessage` 에 POST. 4096자 한도를 4000자 청크로
   분할 순차 전송. markdown 이스케이프 이슈 회피를 위해 `parse_mode` 미지정(plain text).
3. **기본 활성 채널을 `email,telegram` 로 전환**(dispatcher `_resolve_channels` 기본값 +
   `.env.example` `NOTIFY_CHANNELS`). `run_daily_local.sh` 는 `--channels` 미지정으로
   `NOTIFY_CHANNELS` env 를 그대로 사용(코드 변경 불필요).
4. **`slack`/`gmail`(MCP 위임형)은 코드·REGISTRY 등록을 유지하되 기본 비활성**으로 둔다 —
   cloud routine 옵션 보존. 삭제하지 않는 이유: 기존 slack cloud routine 수신을 깨지 않기 위함.
5. **G21 secret 등록**: `SMTP_PASSWORD` 를 `SECRET_ENV_KEYS` 에 추가(`TELEGRAM_BOT_TOKEN`/
   `TELEGRAM_CHAT_ID` 는 기존 등록). 두 adapter 의 `send()` 예외는 `secret_safe_log(str(exc),
   env)` 로 redact 후 `AdapterResult.error` 에 담는다(토큰/비밀번호 로그 노출 차단).

## Consequences

- **로컬 실발송**: `.env` 에 `SMTP_*` / `TELEGRAM_*` 와 `NOTIFY_CHANNELS=email,telegram` 를
  채우면 로컬 파이프라인이 메일·텔레그램을 즉시 발송한다(cloud routine 불필요).
- **보안 함의(검토 필요)**: 로컬 직접 발송은 SMTP 앱 비밀번호와 봇 토큰을 **로컬 `.env`** 에
  저장하고 로컬 머신에서 외부로 송신함을 의미한다(기존 cloud-routine secret-inject 와 다름).
  G21 redaction 으로 로그/산출물 노출은 막지만, `.env` 파일 자체 보호(.gitignore + 파일 권한)는
  사용자 책임. 30-security 의 secret 취급 원칙 준수.
- **MCP 옵션 보존**: cloud routine 을 쓰는 사용자는 `NOTIFY_CHANNELS=slack,gmail` 로 되돌릴 수
  있다(rollback 경로).
- **검증**: smtplib/urllib 는 단위 테스트에서 mock(`tests/unit/test_notify_email.py`,
  `tests/unit/test_notify_telegram.py`) — 외부 연결 없이 호출 인자/청킹/redaction 검증. 실발송은
  사용자가 `.env` 를 채운 뒤 1회 수동 확인(사용자 게이트).
