# ADR-0016 — DeepSeek 백엔드로 Claude Code agentic Stage 4/6 구동

`status: Accepted (구현 2026-06-17)`
`date: 2026-06-17`
`refs: 0009 (claude→zed migration, 본 ADR 이 single-turn deepseek 부분 amend), D-CORE-5, D-CORE-7, G21, infrastructure/llm/, applications/run_daily_local.sh`

## Context

Stage 4(thesis-auditor) / Stage 6(brief-author) 는 파일을 읽고 쓰는 **agentic 스킬**이다
(`$TRAIL_TODAY/04-thesis-candidates.json`, `operations/{date}/daily-brief.md` 산출). 두 후보
구현이 부적합했다:

- **single-turn `DeepSeekAdapter`** (구 `infrastructure/llm/deepseek.py`): DeepSeek chat API
  를 1회 호출해 stdout 만 출력 — tool-execution loop·파일 I/O·skill 본문 주입이 전무해 산출물을
  만들지 못한다. `openai` SDK 의존까지 추가됐다. → agentic 스킬 대체 불가 (D-CORE-7 위반).
- **순수 `claude-cli`**: agentic harness 로 정상 동작하나 Anthropic 구독/ API 키 과금이 필요.

DeepSeek 는 **Anthropic-호환 엔드포인트**(`https://api.deepseek.com/anthropic`)를 공식 제공하며
tool use(tools/tool_use/tool_result)가 Fully Supported 다. Claude Code 연동은 순수 환경변수
설정으로 끝난다(공식 "Use DeepSeek in Claude Code"). 즉 `claude` harness 는 그대로 두고 추론
백엔드만 DeepSeek 로 redirect 할 수 있다.

추가로, 본 저장소는 ADR-0009 에서 Claude Code(`.claude/`) → Zed(`.agents/skills/`, `AGENTS.md`)
로 이전해 `.claude/`·`CLAUDE.md` 가 부재했다. `claude` CLI 는 `CLAUDE.md` 메모리와
`.claude/skills/` 만 인식하므로 브릿지가 필요했다.

## Decision

1. **신규 vendor `claude-cli-deepseek`** (`infrastructure/llm/claude_code_deepseek.py`):
   `ClaudeCliAdapter` 를 상속해 cmd 조립·binary 해석·실행은 재사용하고, `_subprocess_env()`
   override 로 `claude` 자식 프로세스 env 를 DeepSeek 로 redirect 한다.
   - `ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic` (강제)
   - `ANTHROPIC_AUTH_TOKEN` = 기존 `DEEPSEEK_API_KEY` 재사용 (강제, 신규 secret 0)
   - `ANTHROPIC_API_KEY` 는 자식 env 에서 **제거** → Anthropic $0 보장 + 인증 충돌
     (anthropics/claude-code#67861) 차단
   - 모델/effort 6종(`deepseek-v4-pro[1m]` / `deepseek-v4-flash` / effort=max)은 `setdefault`
     (사용자 env override 허용)
   - vendor 종속을 본 bounded adapter 한 곳에 가둔다 (D-CORE-7).
2. **dispatcher 기본 vendor 를 `claude-cli-deepseek` 로 전환.** rollback 은 순수
   `claude-cli`(Anthropic) 로 `LLM_VENDOR` override. `run_daily_local.sh` 가
   `LLM_VENDOR="${LLM_VENDOR:-claude-cli-deepseek}"` 로 배포 기본값을 박는다.
3. **single-turn `DeepSeekAdapter`/`deepseek.py`/pyproject `[llm]`(openai) extra 회수.**
   `openai` SDK 의존 제거(D-CORE-5: 의존성 최소화).
4. **Claude Code 브릿지(git 커밋, 인프라 취급)**: `CLAUDE.md`→`AGENTS.md`,
   `.claude/skills`→`.agents/skills` 상대 심볼릭. `.claude/commands/*` 는 **만들지 않는다**
   — 스킬은 슬래시(`/`)로 직접 호출 불가하고, headless 슬래시/스킬 수동 호출은 Agent SDK
   import 가 필요해 과하다. 대신 `run_daily_local.sh` 가 **explicit-path 지시문 프롬프트**
   (".agents/skills/<name>/SKILL.md 를 읽고 거래일 X 로 실행 …")로 dispatch 한다.
5. `DEEPSEEK_API_KEY` 를 `SECRET_ENV_KEYS` 에 추가 (G21 — 주입 secret 로그 redaction).

## Consequences

- **비용**: Anthropic $0(구독/키 불필요, 호출 안 감). DeepSeek 종량(기존 `DEEPSEEK_API_KEY`).
  agentic 루프 토큰량을 감안해 subagent/haiku 는 `deepseek-v4-flash` 권장값 채택.
- **검증 필요**: DeepSeek 계정의 v4 모델 접근. 첫 실행 시 DeepSeek 사용량↑ + Anthropic 콘솔 0
  확인. DeepSeek-백엔드 Claude Code 가 5필드 thesis / falsifier guard / JSON envelope(D-Q-2)
  를 충실히 따르는지 초기 산출 schema 점검(G1~G8 하류 게이트).
- **브릿지 인프라**: `claude` CLI 는 production LLM harness 의존성으로 git 커밋된다(`.kiro` 는
  dev 전용이라 여전히 gitignore). 심볼릭 무결성은 `tests/architecture/test_claude_code_bridge.py`
  가 가드.
- **불변**: G9(자동매매 금지) — read/research 전용 chain 유지. run_daily_local.sh graceful degrade.
