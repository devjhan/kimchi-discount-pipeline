# ADR-0009: Claude Code → Zed Agent 마이그레이션

> **Amended by ADR-0016 (2026-06-17)**: 본 ADR 이 채택했던 single-turn DeepSeek
> dispatch(`infrastructure/llm/deepseek.py`)는 회수됐다. agentic Stage 4/6 은
> `claude` harness + DeepSeek Anthropic-호환 백엔드(vendor `claude-cli-deepseek`)로
> 구동하며, `.claude/skills`·`CLAUDE.md` 심볼릭 브릿지가 다시 도입됐다. 상세는 ADR-0016.
>
> **Body는 historical**: 하단 §2~§8 은 2026-06-10 시점의 마이그레이션 *계획*을 문서화하며,
> 일부(D-1 skill 경로, D-2 hook 파기, D-4 symlink)는 실행됐고 일부(D-3 DeepSeek
> single-turn)는 ADR-0016으로 회수됐다. 현행 기준은 ADR-0016 + ADR-0011 참조.

| 속성 | 값 |
|---|---|
| **ADR ID** | 0009 |
| **상태** | Accepted (implemented, body는 historical) |
| **일자** | 2026-06-10 |
| **Amended by** | ADR-0011, ADR-0016 |
| **결정자** | 사용자 |
| **범위** | Agent runtime, skill storage, LLM dispatch, hook enforcement, 문서 전반 |

---

## 1. 문제 정의 (Problem Statement)

`kimchi-discount-pipeline` 프로젝트는 Claude Code 생태계에 구조적으로 결합되어 있다. Claude Code → Zed Agent로 이주하면서 아래 3개 축에서 호환성 단절이 발생했고, 이는 파이프라인 전체 실행불능 상태다.

| Claude Code 의존 요소 | Zed 에서의 상태 | 영향 |
|---|---|---|
| **Hooks** (8종, `.claude/settings.json` + shell scripts) | Zed에 hook 개념 **부재** | `.env` guard, anti-pattern 차단, citation gate, lint directive 등 runtime enforcement 전면 소멸 |
| **Skills** (9종, `.claude/skills/`) | Zed의 skill 포맷/경로(**`.agents/skills/`**)와 **불일치** | Stage 0/2/4/6 LLM task 및 audit/interactive skill 호출 불가 |
| **`claude -p` CLI** (LLM 런타임) | Zed는 자체 agent가 LLM을 호출하므로 `claude -p` subprocess **의미 소멸** | `run_daily_local.sh` Stage 4/6 + notify dispatch의 agentic loop 전체 중단 |

본 결정은 Claude Code 종속성을 완전히 제거하고, Zed + DeepSeek API 기반 실행 가능 구조로 재구성하기 위한 마이그레이션 계획을 정의한다.

---

## 2. 현재 상태 전체 인벤토리 (Context Inventory)

### 2.1 Claude Code Hooks — 8종

| # | Hook Path | Hook Event | 역할 | 파기/보존 |
|---|---|---|---|---|
| 1 | `bootstrap/inject_session_state/` | SessionStart | KST 경로/trail/positions/portfolio 주입 | **보존** (Zed Project Rules로 기능 이관) |
| 2 | `context/inject_investment_contract/` | UserPromptSubmit | cross-cutting contract 주입 | **파기** |
| 3 | `context/inject_directive_context/` | UserPromptSubmit | 코딩 directive 본문 주입 | **파기** |
| 4 | `context/inject_guidelines/` | UserPromptSubmit | hard-guards 룰 주입 | **파기** |
| 5 | `guard/pre_env_guard/` | PreToolUse | `.env` 직접 접근 차단 | **파기** (→ pre-commit + chmod 0600) |
| 6 | `guard/block_anti_patterns/` | PreToolUse Write/Edit | D-PY-1/D-SH-1/D-CFG-1/D-SEC-1 차단 | **파기** (→ pre-commit lint) |
| 7 | `quality/brief_citation_gate/` | PostToolUse Write/Edit + Stop | 숫자 citation 의무 검사 | **파기** (→ Python pipeline validation) |
| 8 | `quality/lint_directives/` | PostToolUse Write/Edit | D-PY-2/3/5 등 검사 | **파기** (→ ruff pre-commit) |
| ~ | (미구현 9종) | — | `pre_no_autotrade`, `post_redact_secrets`, `post_forbidden_language`, `post_falsifier_validator`, `post_asymmetry_validator`, `stop_sample_gate` 등 | **기록 보존** (파기된 hook 목록 문서화) |

### 2.2 Claude Code Skills — 9종

| # | Skill Folder | Stage | 핵심 컨텐츠 |
|---|---|---|---|
| 1 | `investment-stage0-regime-labeler` | Stage 0 | SKILL.md + `domain/` (빈 폴더) |
| 2 | `investment-stage2-quality-lens` | Stage 2 | SKILL.md + `domain/` (빈 폴더) |
| 3 | `investment-stage4-thesis-auditor` | Stage 4 | SKILL.md + `domain/`(3개 md: thesis-fields-format, falsifier-validation, edge-source-classification) |
| 4 | `investment-stage6-brief-author` | Stage 6 | SKILL.md + `domain/` (빈 폴더) |
| 5 | `investment-audit-process` | Audit | SKILL.md + `domain/` (빈 폴더) |
| 6 | `investment-audit-outcome` | Audit | SKILL.md + `domain/` (빈 폴더) |
| 7 | `investment-ingest-external-signal` | Ingest | SKILL.md + `domain/` (빈 폴더) |
| 8 | `investment-policy-profiler` | Policy | SKILL.md (domain/ 없음) |
| 9 | `_shared/investment/` | Shared bootstrap | `bootstrap.md` (260줄 — cross-cutting 규약, 경로 표기, forbidden language, thesis 5필드 등) |

### 2.3 LLM Runtime (`infrastructure/llm/`)

```
infrastructure/llm/
├── __init__.py       # REGISTRY dict (현재 claude-cli 1개 등록)
├── adapter.py        # LlmAdapter ABC + LlmResult dataclass
├── claude_cli.py     # ClaudeCliAdapter — subprocess claude -p
└── dispatcher.py     # invoke(prompt, vendor, allowed_tools) → LlmResult
```

**작동 원리**: `run_daily_local.sh`가 `python -m infrastructure.llm.dispatcher --prompt "/investment-stage4-thesis-auditor $DATE" --allowed-tools "..."` 호출 → dispatcher가 `LLM_VENDOR` env(기본 `claude-cli`)로 adapter 선택 → `ClaudeCliAdapter.invoke()`가 `subprocess.run(["claude", "-p", prompt, "--allowed-tools", ...])` 실행.

**핵심 seam**: `__init__.py`의 REGISTRY에 adapter class 1개 추가 + `LLM_VENDOR=deepseek` 설정 → 새 vendor로 전환. 기존 `run_daily_local.sh`는 **수정 불필요** (F-13 설계 의도).

### 2.4 Claude Code CLI 호출처 (`run_daily_local.sh`)

`applications/run_daily_local.sh` 내부의 LLM 호출은 3곳:

| Line | Section | 호출 | 현재 명령 |
|---|---|---|---|
| 136-140 | Stage 4 thesis-auditor | `python -m infrastructure.llm.dispatcher --prompt "/investment-stage4-thesis-auditor $DATE_KST"` | dispatcher 경유 → `claude -p` |
| 149-154 | Stage 6 brief-author | `python -m infrastructure.llm.dispatcher --prompt "/investment-stage6-brief-author $DATE_KST"` | dispatcher 경유 → `claude -p` |
| 178-182 | MCP notify dispatch | `python -m infrastructure.llm.dispatcher --prompt "..." --allowed-tools "Read,$SLACK_MCP_TOOL,$GMAIL_MCP_TOOL"` | dispatcher 경유 → MCP relay |

**핵심**: `run_daily_local.sh`는 이미 dispatcher 패턴으로 추상화되어 있으므로, vendor 교체만으로 LLM 백엔드 전환이 완료된다. 단, MCP notify dispatch(line 170-183)는 Claude Code MCP connector에 의존하는 구조이므로 별도 전환 필요.

### 2.5 문서 내 Claude Code 잔존 참조

| 파일 | 참조 형태 |
|---|---|
| `AGENTS.md` | L100-115: 기술 스택 "Agent runtime: Claude Code custom skills", L102: "claude -p + MCP 도구로 발송", L128: `CLAUDE.md → AGENTS.md symlink`, L187-191: `.claude/hooks/`, `.claude/skills/` |
| `CLAUDE.md` (root symlink → AGENTS.md) | `.gitignore` L84: `CLAUDE.md` gitignore 등록 (symlink) |
| `.claude/hooks/AGENTS.md` | 전체가 hook 시스템 문서 — L13-21: 활성 hook 목록, L87-103: hook spec (stdin JSON, exit code 2=reject) |
| `.claude/skills/_shared/investment/bootstrap.md` | L14: `CLAUDE.md`, L69: `$SKILLS_SHARED_DIR` = `.claude/skills/_shared/investment`, L300: `CLAUDE.md` |
| 모든 skill `SKILL.md` | 각각 `CLAUDE.md`, `$SKILLS_SHARED_DIR/bootstrap.md` 참조 |
| `governance/specs/deployment-residency.md` | L36: "Anthropic Claude Code Routines", L53: "CLAUDE.md" |
| `governance/specs/hard-guards.md` | L3: `CLAUDE.md`, L125: `$SKILLS_SHARED_DIR/bootstrap.md`, L322: `CLAUDE.md`, L335: `CLAUDE.md` |
| `governance/directives/AGENTS.md` | L6: hook 시스템 참조 (`block_anti_patterns.sh` 등), L68-71: hook 작성 절차 |
| `governance/directives/` 내 `CLAUDE.md` | `AGENTS.md`로의 symlink 또는 동일 내용 |
| `.claude/settings.json` | 전체 Claude Code hook config (SessionStart, UserPromptSubmit, PreToolUse, PostToolUse, Stop) |
| `domains/policy/AGENTS.md` | L28-33: "구현(Claude skill / API)은 `_boundary` 뒤" |
| `domains/risk_engine/AGENTS.md` | L57-59: "③ .claude/settings.json Bash deny" |
| `tests/unit/test_llm_dispatcher.py` | L1-4: "claude -p 호출의 vendor-neutral seam" |

### 2.6 `.env` API 키 현황 (`.env.example` 기준)

```
DART_API_KEY=              # 필수
KIS_APP_KEY=               # 필수
KIS_APP_SECRET=            # 필수
KIS_ACCOUNT_NUMBER=        # 옵션
FRED_API_KEY=              # 옵션
TELEGRAM_BOT_TOKEN=        # 옵션
TELEGRAM_CHAT_ID=          # 옵션
NOTIFY_CHANNELS=           # 옵션 (slack,gmail)
NOTIFY_SLACK_CHANNEL=      # 옵션
NOTIFY_EMAIL_TO=           # 옵션
NOTIFY_EMAIL_FROM=         # 옵션
```

**LLM API 키 현황**: `.env.example`에 `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `DEEPSEEK_API_KEY` **모두 없음**. 신규 `DEEPSEEK_API_KEY` 필드 추가 필요.

---

## 3. 마이그레이션 결정 (Decisions)

### D-1: Skill 저장소 경로 → `.agents/skills/`

**결정**: Claude Code `.claude/skills/` → Zed 프로젝트-로컬 `.agents/skills/` 로 `git mv`.

**근거**: Zed 공식 문서(https://zed.dev/docs/ai/skills)에 따르면 프로젝트-로컬 skill은 `<worktree>/.agents/skills/` 에 위치. 전역 `~/.agents/skills/` 는 사용하지 않으며, 모든 investment skill은 프로젝트 inner scope로 유지.

**변환**: 각 skill folder의 `SKILL.md` frontmatter를 Zed 포맷(`name`, `description`)으로 변환. `allowed-tools` 필드는 Zed skill 포맷에 없으므로 제거(본문에 우회 기재). 기존 `domain/` 하위 참조 파일은 그대로 유지.

### D-2: Hook 전면 파기 (inject_session_state 제외)

**결정**: 8개 hook 중 `inject_session_state`만 기능 보존. 나머지 7개는 **파기** + 문서에 파기 사실과 대체 수단 기록.

| 파기 Hook | 대체 수단 |
|---|---|
| `context/inject_investment_contract/` | `AGENTS.md`에 contract 본문 이미 포함 — 별도 inject 불필요 |
| `context/inject_directive_context/` | `AGENTS.md` + `governance/directives/` 문서 — 정적 context로 충분 |
| `context/inject_guidelines/` | `AGENTS.md` + `governance/specs/hard-guards.md` — 정적 context로 충분 |
| `guard/pre_env_guard/` | chmod 0600 + `.gitignore` + `infrastructure/_common/utils.py`에서만 `.env` 접근 |
| `guard/block_anti_patterns/` | `.pre-commit-config.yaml`에 ruff + custom lint rules 추가 |
| `quality/brief_citation_gate/` | `applications/daily_pipeline.sh` Stage 6 후 Python validation step 추가 |
| `quality/lint_directives/` | `.pre-commit-config.yaml`에 ruff 포맷팅/lint 통합 |

**보존**: `inject_session_state`의 **기능**(KST 경로, trail 파일 목록, positions, portfolio 컨텍스트)은 `AGENTS.md`의 "SessionStart 컨텍스트 주입" 섹션으로 이관. 실제 구현은 `infrastructure/_common/bootstrap_context.py` (신규)가 담당 — cron 실행 시 `run_daily_local.sh`가 이 Python 모듈을 먼저 호출해 stdout으로 context를 출력, `AGENTS.md` 상단에 context block으로 포함.

### D-3: LLM 런타임 → DeepSeek API

**결정**: `claude -p` subprocess 호출을 DeepSeek API(`api.deepseek.com`, OpenAI-compatible)로 교체.

**근거**:
- `.env`에 Anthropic 키 없음, DeepSeek 키 신규 추가
- `infrastructure/llm/` adapter 패턴(REGISTRY)이 vendor 교체를 위해 이미 설계됨 (F-13)
- DeepSeek API는 OpenAI SDK 호환 — `openai` Python 패키지로 호출 가능
- 기존 Claude Code MCP connector(notify dispatch)는 표준 API로 전환

**구현 방식**:
```
infrastructure/llm/deepseek.py (신규)
  └── DeepSeekAdapter(LlmAdapter)
       name = "deepseek"
       invoke() → openai.OpenAI(base_url="https://api.deepseek.com").chat.completions.create()
```

**등록**:
```python
# infrastructure/llm/__init__.py
from infrastructure.llm.deepseek import DeepSeekAdapter
REGISTRY["deepseek"] = DeepSeekAdapter
```

**환경변수**: `LLM_VENDOR=deepseek` + `DEEPSEEK_API_KEY=<key>` in `.env`

**MCP notify 대체**: 기존 Claude Code MCP(Slack/Gmail connector) 대신, `infrastructure/notify/` dispatcher를 DeepSeek API로 직접 호출해 JSON 응답을 파싱 → NotifierAdapter 호출. Slack/Gmail 어댑터는 이미 `infrastructure/notify/`에 Python으로 구현되어 있음. MCP relay 없이 직접 호출.

### D-4: CLAUDE.md 심볼릭 링크 처리

**결정**: root `CLAUDE.md → AGENTS.md` symlink는 **제거하지 않음** (Zed 프로젝트 rule은 `AGENTS.md`를 읽으므로 무해). `.gitignore`에 `CLAUDE.md`가 등록되어 있어 이미 git untracked.

다만, 모든 문서 내 `CLAUDE.md` 참조는 `AGENTS.md`로 변경한다.

### D-5: `.claude/` 디렉토리 전체 제거

**결정**: Migration 완료 검증 후 `.claude/` 디렉토리 완전 삭제 (`.gitignore`에서도 관련 라인 제거, 단 `.claude/*` gitignore는 `.zed/*` 등 필요 시 조정).

---

## 4. 실행 시퀀스 (Migration Roadmap)

### Phase 0 — 전제 조건 확인 (현재)
- [ ] 본 ADR-0027 사용자 confirm
- [ ] `pip install openai` (DeepSeek API 호환)
- [ ] `.env`에 `DEEPSEEK_API_KEY` 추가 (사용자 수동)

### Phase 1 — DeepSeek Adapter 구현 + dispatch 전환

**1.1** `infrastructure/llm/deepseek.py` 신규 작성
- `DeepSeekAdapter(LlmAdapter)` 구현
- `name = "deepseek"`
- `invoke(prompt, allowed_tools, dry_run)` → `openai.OpenAI(base_url="https://api.deepseek.com", api_key=os.environ["DEEPSEEK_API_KEY"]).chat.completions.create(model="deepseek-chat", messages=[{"role": "user", "content": prompt}])`
- `allowed_tools`는 DeepSeek function calling 또는 system prompt 제약으로 변환
- `status="skipped"` 조건: `DEEPSEEK_API_KEY` 미설정

**1.2** `infrastructure/llm/__init__.py`에 DeepSeekAdapter 등록
```python
from infrastructure.llm.deepseek import DeepSeekAdapter
REGISTRY["deepseek"] = DeepSeekAdapter
```

**1.3** `tests/unit/test_llm_dispatcher.py`에 deepseek 테스트 추가
- `test_registry_has_deepseek`
- `test_deepseek_dry_run`
- `test_deepseek_api_key_absent_skips`

**1.4** ClaudeCliAdapter **유지** (rollback safety). 기본 vendor만 `deepseek`로 변경.

### Phase 2 — Skill 변환 (`.claude/skills/` → `.agents/skills/`)

**2.1** `.agents/skills/` 디렉토리 생성

**2.2** 각 skill `git mv` (git lines 보존):
```bash
git mv .claude/skills/investment-stage0-regime-labeler   .agents/skills/investment-stage0-regime-labeler
git mv .claude/skills/investment-stage2-quality-lens      .agents/skills/investment-stage2-quality-lens
git mv .claude/skills/investment-stage4-thesis-auditor    .agents/skills/investment-stage4-thesis-auditor
git mv .claude/skills/investment-stage6-brief-author      .agents/skills/investment-stage6-brief-author
git mv .claude/skills/investment-audit-process            .agents/skills/investment-audit-process
git mv .claude/skills/investment-audit-outcome            .agents/skills/investment-audit-outcome
git mv .claude/skills/investment-ingest-external-signal   .agents/skills/investment-ingest-external-signal
git mv .claude/skills/investment-policy-profiler          .agents/skills/investment-policy-profiler
git mv .claude/skills/_shared                             .agents/skills/_shared
```

**2.3** 각 `SKILL.md` frontmatter 수정 (필요 시)
- `allowed-tools:` 제거 (Zed skill 포맷 불필요)
- `description:`이 Zed catalog 50KB budget 이내인지 확인

**2.4** `bootstrap.md`의 `$SKILLS_SHARED_DIR` 경로 업데이트:
```
- | `$SKILLS_SHARED_DIR` | `.agents/skills/_shared/investment` |
```
(변경 없음 — `_shared` 폴더가 함께 이동했으므로 상대 경로 동일)

### Phase 3 — Hook 파기 + inject_session_state 기능 이관

**3.1** `inject_session_state` 기능 분석 및 Python 재구현
- `infrastructure/_common/bootstrap_context.py` 신규
- `def get_bootstrap_context(date_kst: str) -> str`: KST 경로, trail 파일 목록, positions, portfolio 컨텍스트를 plain text로 반환
- `run_daily_local.sh` 0a 단계 이후 호출 → `AGENTS.md` 상단에 주입할 context 블록 출력

**3.2** 파기된 hook 문서화
- `governance/decisions/0027-hook-disposition.md` 신규 — 파기된 7개 hook의 역할, 파기 사유, 대체 수단 일람표

**3.3** `.claude/settings.json` 제거 (hook config 더 이상 불필요)

**3.4** `.claude/hooks/` 디렉토리 전체 삭제 (단, `inject_session_state` entrypoint/validator는 Phase 3.1 코드로 대체 후 삭제)

### Phase 4 — 문서 전면 갱신

**4.1** `AGENTS.md` 수정 대상
| 섹션 | 변경 |
|---|---|
| 기술 스택 - Agent runtime | `Claude Code custom skills` → `Zed Agent project skills (.agents/skills/)` |
| 기술 스택 - Notification | `claude -p + MCP 도구` → `infrastructure/notify/ dispatcher (Python native)` |
| 기술 스택 - Scheduling | "cloud routine...cloud_routine_run.sh deprecated" 유지, "Anthropic Claude Code Routines" 제거 |
| 기술 스택 - Hard guards | `.claude/hooks/` → `pre-commit hooks + pipeline validation (governance/decisions/0027-hook-disposition.md)` |
| 디렉토리 구조 - `.claude/` 블록 | → `.agents/skills/` 블록으로 교체, `.claude/settings.json`, hooks 삭제 반영 |
| 디렉토리 구조 - `CLAUDE.md → AGENTS.md` | `# symlink (Claude Code 호환)` → `# symlink (legacy, Zed 미사용 — .gitignore 등록)` |
| NOTES - 외부 신호 SOP | `/ingest-external-signal` → `investment-ingest-external-signal` (Zed skill reference) |

**4.2** `governance/specs/deployment-residency.md`
- L36: `Anthropic Claude Code Routines (cloud)` → `Cloud LLM Routines` (또는 paragraph 삭제 — 현재 비활성)
- L53: `CLAUDE.md` → `AGENTS.md`

**4.3** `governance/specs/hard-guards.md`
- L3: `CLAUDE.md` → `AGENTS.md`
- L125: `$SKILLS_SHARED_DIR/bootstrap.md` → 유지 (이미 업데이트됨)
- L322, L335: `CLAUDE.md` → `AGENTS.md`

**4.4** `governance/directives/` 내 `CLAUDE.md`, `AGENTS.md`
- 두 파일이 동일 내용임을 확인
- `CLAUDE.md`가 symlink면 유지, 아니면 `AGENTS.md`만 남기고 삭제
- 본문 내 hook 참조(block_anti_patterns.sh 등) → Phase 3 결정 반영

**4.5** `domains/*/AGENTS.md` 파일들
- `domains/policy/AGENTS.md` L28-33: `Claude skill / API` → `Zed skill / DeepSeek API`
- `domains/risk_engine/AGENTS.md` L57-59: `.claude/settings.json` 참조 → 제거

**4.6** 모든 skill `SKILL.md` 내 `CLAUDE.md` 참조 → `AGENTS.md`로 변경

**4.7** `.gitignore`
- L84: `# Claude-Code - local symlink to AGENTS.md` → `# Legacy symlink to AGENTS.md (kept for compatibility, not tracked)`
- `.claude/` 관련 라인 확인 및 필요 시 제거 (hooks `.claude/hooks/_audit.log` 등)

### Phase 5 — `.claude/` 디렉토리 최종 제거

**5.1** `.claude/settings.json` 제거 (Phase 3.3과 중복 — 여기서 확정)

**5.2** `.claude/settings.local.json` 제거 (머신-로컬, gitignore 대상)

**5.3** `.claude/hooks/` 디렉토리 전체 제거

**5.4** `.claude/agents/` 디렉토리 제거 (현재 빈 폴더)

**5.5** `.claude/` 디렉토리가 완전히 비면 루트 `.claude/` 제거

### Phase 6 — 통합 검증

**6.1** Python test suite 실행
```bash
python -m pytest tests/ -x -q --tb=short
```

**6.2** `infrastructure/llm/dispatcher` dry-run 검증
```bash
python -m infrastructure.llm.dispatcher --vendor deepseek --dry-run --prompt "test"
# → status=dry_run, vendor=deepseek
```

**6.3** `run_daily_local.sh` dry-run (주말/휴일 KST 기준)
```bash
bash applications/run_daily_local.sh --date 2026-06-07  # 토요일
# → pre-stage4 정상 실행, Stage 4/6 deepseek skip(API 키 없으면), notify skip
```

**6.4** Lint/Ruff 통과
```bash
ruff check .
```

**6.5** Zed agent가 `.agents/skills/`를 인식하는지 확인 (Zed 재시작 → AI > Skills > Project 탭)

---

## 5. Commit 전략

| # | Commit message | 포함 변경 |
|---|---|---|
| 1 | `feat(migrate): add DeepSeek LLM adapter (F-13 vendor swap)` | `infrastructure/llm/deepseek.py` 신규, `__init__.py` REGISTRY 추가, test |
| 2 | `refactor(migrate): move skills from .claude/ to .agents/ (git mv)` | `.claude/skills/` → `.agents/skills/` 전체 `git mv` |
| 3 | `feat(migrate): add bootstrap_context.py and document hook disposition` | `infrastructure/_common/bootstrap_context.py` 신규, `governance/decisions/0027-hook-disposition.md` 신규 |
| 4 | `chore(migrate): remove .claude/hooks/ directory` | `.claude/hooks/` 전체 삭제, `.claude/settings.json` 삭제 |
| 5 | `docs(migrate): update AGENTS.md and governance docs for Zed migration` | `AGENTS.md`, `governance/specs/`, `governance/directives/`, `domains/*/AGENTS.md`, 모든 `SKILL.md` 내 CLAUDE.md → AGENTS.md |
| 6 | `chore(migrate): remove .claude/ directory, update .gitignore` | `.claude/` 최종 제거, `.gitignore` 갱신 |
| 7 | `chore(migrate): add ADR-0027 migration decision record` | `governance/decisions/0027-claude-code-to-zed-migration.md` (본 문서) |

**브랜치 전략**: `feature/claude-code-to-zed-migration` 브랜치 생성 → 위 7개 커밋 순차 → `main`에 merge.

---

## 6. 마이그레이션 후 디렉토리 구조 (Target State)

```diff
kimchi-discount-pipeline/
├── AGENTS.md                          # [수정] Zed project context (Claude Code ref 제거)
├── CLAUDE.md → AGENTS.md              # [유지] legacy symlink (.gitignore 등록)
│
├── .agents/                           # [신규] Zed project-local skills
│   └── skills/
│       ├── _shared/
│       │   └── investment/
│       │       └── bootstrap.md       # [이동] (git mv) — CLAUDE.md → AGENTS.md 수정
│       ├── investment-stage0-regime-labeler/
│       │   ├── SKILL.md              # [이동] allowed-tools 제거
│       │   └── domain/               # (empty)
│       ├── investment-stage2-quality-lens/
│       │   ├── SKILL.md
│       │   └── domain/               # (empty)
│       ├── investment-stage4-thesis-auditor/
│       │   ├── SKILL.md
│       │   └── domain/
│       │       ├── thesis-fields-format.md
│       │       ├── falsifier-validation.md
│       │       └── edge-source-classification.md
│       ├── investment-stage6-brief-author/
│       │   ├── SKILL.md
│       │   └── domain/               # (empty)
│       ├── investment-audit-process/
│       │   ├── SKILL.md
│       │   └── domain/               # (empty)
│       ├── investment-audit-outcome/
│       │   ├── SKILL.md
│       │   └── domain/               # (empty)
│       ├── investment-ingest-external-signal/
│       │   ├── SKILL.md
│       │   └── domain/               # (empty)
│       └── investment-policy-profiler/
│           └── SKILL.md
│
├── infrastructure/
│   ├── _common/
│   │   ├── utils.py
│   │   └── bootstrap_context.py      # [신규] inject_session_state 기능
│   └── llm/
│       ├── __init__.py               # [수정] REGISTRY["deepseek"] 추가
│       ├── adapter.py                # [유지]
│       ├── claude_cli.py             # [유지] rollback safety
│       ├── deepseek.py               # [신규] DeepSeekAdapter
│       └── dispatcher.py             # [유지] (기본 vendor deepseek로)
│
├── applications/
│   └── run_daily_local.sh            # [수정] MCP notify → Python notify relay
│
├── governance/
│   ├── decisions/
│   │   ├── 0027-claude-code-to-zed-migration.md   # [신규] 본 ADR
│   │   └── 0027-hook-disposition.md               # [신규] 파기 hook 기록
│   ├── specs/
│   │   ├── deployment-residency.md   # [수정] Claude Code ref 제거
│   │   └── hard-guards.md            # [수정] CLAUDE.md → AGENTS.md
│   └── directives/
│       ├── AGENTS.md                 # [수정] hook ref 제거
│       └── CLAUDE.md                 # [확인 후 처리] symlink면 유지, 아니면 제거
│
├── domains/*/AGENTS.md               # [수정] Claude Code ref 제거
│
├── tests/unit/test_llm_dispatcher.py # [수정] deepseek test 추가
│
├── .gitignore                        # [수정] .claude/ 관련 라인 정리
│
└── .claude/                          # [제거] 전체 디렉토리
```

---

## 7. 리스크 및 열린 이슈

| Risk | 심각도 | 완화 |
|---|---|---|
| **DeepSeek API로 Claude Code 수준의 agentic loop 재현 불가** | 🔴 High | `claude -p`의 "skill slash-command + file read/write multi-step"은 agentic loop다. DeepSeek API는 single-turn chat completion에 가까움. **경감**: Stage 4/6 prompt에 file path + task description을 포함한 single comprehensive prompt로 재구성. multi-turn 필요 시 Python이 여러 API call orchestrate. |
| **MCP notify (Slack/Gmail) dispatch 재구현** | 🟡 Medium | 기존 `claude -p`가 MCP 도구(Slack/Gmail)를 호출해 알림 발송. DeepSeek은 MCP connector가 없음. **경감**: `infrastructure/notify/` dispatcher가 이미 Python으로 구현되어 있음. `run_daily_local.sh` line 170-183을 Python native notify 호출로 대체. |
| **DeepSeek API 키 미보유 시 전체 LLM stage skip** | 🟢 Low | `ClaudeCliAdapter`와 동일하게 `status="skipped"` + 경고 로그 (graceful degrade). |
| **Zed skill을 cron에서 호출 불가** | 🟡 Medium | Zed skill은 interactive agent 전용. cron 실행(headless)은 Zed agent를 거치지 않음. **경감**: `.agents/skills/`의 SKILL.md + domain/ 파일을 Python이 직접 읽어 DeepSeek API prompt로 구성. prompt content는 skill 본문을 재사용. |
| **나열되지 않은 숨은 Claude Code 참조** | 🟢 Low | Phase 4 문서 갱신 + `grep -r "claude\|CLAUDE\|anthropic" --include="*.{md,py,sh,yaml}"` 전수 검사. |

---

## 8. Confirm 체크리스트

사용자 확인 요청 사항:

- [ ] **D-1**: `.agents/skills/` 경로 + 프로젝트 inner scope만 사용 — 동의?
- [ ] **D-2**: inject_session_state 제외 모든 hook 파기 + 문서화 — 동의?
- [ ] **D-3**: DeepSeek API로 LLM 전환 (`.env`에 `DEEPSEEK_API_KEY` 추가 필요) — 동의?
- [ ] **D-4**: `CLAUDE.md` symlink 유지, 문서 내 참조는 `AGENTS.md`로 변경 — 동의?
- [ ] **D-5**: `.claude/` 디렉토리 전체 제거 — 동의?
- [ ] **전체 Phase 0~6 로드맵** — 동의?
- [ ] **Commit 전략 (브랜치 + 7개 커밋)** — 동의?

**추가 확인**:
- `DEEPSEEK_API_KEY` 는 사용자가 수동으로 `.env`에 추가하는 것으로 충분한가?
- Stage 4/6의 headless cron 실행 시 multi-turn agentic loop이 필요한가, 아니면 single-turn comprehensive prompt로 충분한가?
- Notify dispatch (Slack/Gmail) 방식: Python `infrastructure/notify/` dispatcher를 직접 호출? 아니면 DeepSeek API function calling으로 Slack/Gmail webhook relay?

---

> **확정 후 Phase 1 작업에 즉시 착수합니다.**
