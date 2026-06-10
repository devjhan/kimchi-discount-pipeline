# Hook Disposition — Claude Code → Zed Migration

| 속성 | 값 |
|---|---|
| **ADR** | 0027 (Sub-document) |
| **일자** | 2026-06-10 |
| **마이그레이션** | Claude Code → Zed |

---

## 배경

Claude Code 는 SessionStart / UserPromptSubmit / PreToolUse / PostToolUse / Stop
event 에 shell script hook 을 등록할 수 있다 (`.claude/settings.json`).
Zed Agent 는 이 hook 시스템을 지원하지 않는다.

8개 구현된 hook 중 **7개를 파기**하고, `inject_session_state`(SessionStart)의
**기능만** Python 모듈로 재구현하였다.

---

## 파기된 Hook 일람

### 1. `context/inject_investment_contract` (UserPromptSubmit)

| 속성 | 내용 |
|---|---|
| **역할** | investment 키워드 매칭 시 bootstrap.md §1/§3/§5/§7 을 additionalContext 로 주입 |
| **파기 사유** | `AGENTS.md`에 contract 본문이 이미 포함. Zed의 Project Rules(`AGENTS.md`) 가 대체 |
| **대체 수단** | 없음 (정적 context 로 충분) |

### 2. `context/inject_directive_context` (UserPromptSubmit)

| 속성 | 내용 |
|---|---|
| **역할** | 파일 확장자/키워드 매칭 시 `governance/directives/` 의 directive 본문 주입 |
| **파기 사유** | Zed는 작성 시 Zed의 자동 context 주입 + `AGENTS.md`의 정적 rule 로 충분 |
| **대체 수단** | 없음 (정적 context + project rules) |

### 3. `context/inject_guidelines` (UserPromptSubmit)

| 속성 | 내용 |
|---|---|
| **역할** | hard-guards 관련 룰 주입 |
| **파기 사유** | `AGENTS.md` + `governance/specs/hard-guards.md` 정적 참조로 대체 가능 |
| **대체 수단** | 없음 (정적 context) |

### 4. `guard/pre_env_guard` (PreToolUse Read/Bash/Write/Edit)

| 속성 | 내용 |
|---|---|
| **역할** | `.env` 직접 접근 차단 — Read/Bash/Write/Edit 훅에서 `.env` 패턴 매칭 시 reject (exit 2) |
| **파기 사유** | Zed에 PreToolUse 개념 없음 |
| **대체 수단** | 3중 방어: (1) chmod 0600 로 OS 레벨 보호 (2) `.gitignore` 등록 (3) `infrastructure/_common/utils.py` 만 `.env` read 허용 |

### 5. `guard/block_anti_patterns` (PreToolUse Write/Edit)

| 속성 | 내용 |
|---|---|
| **역할** | D-PY-1 / D-SH-1 / D-CFG-1 / D-SEC-1 anti-pattern 즉시 차단 |
| **파기 사유** | Zed에 PreToolUse 개념 없음 |
| **대체 수단** | `.pre-commit-config.yaml` 에 `ruff` lint + custom rules 추가 검토. 정기 `ruff check .` |

### 6. `quality/brief_citation_gate` (PostToolUse Write/Edit + Stop)

| 속성 | 내용 |
|---|---|
| **역할** | brief 숫자 citation 의무 검사 — `Source@ts=value` 형식 확인, 미준수 시 reject |
| **파기 사유** | Zed에 PostToolUse/Stop 개념 없음 |
| **대체 수단** | `applications/daily_pipeline.sh` Stage 6 이후 Python validation step 추가 예정 |

### 7. `quality/lint_directives` (PostToolUse Write/Edit)

| 속성 | 내용 |
|---|---|
| **역할** | D-PY-2/3/5 / D-CFG-2/3 검사 (M1 dry-run) |
| **파기 사유** | Zed에 PostToolUse 개념 없음 |
| **대체 수단** | `.pre-commit-config.yaml` + `ruff check` 로 대체 |

---

## 보존된 기능: `inject_session_state`

| 속성 | 내용 |
|---|---|
| **원본** | `.claude/hooks/bootstrap/inject_session_state/` (entrypoint.sh + validator.py) |
| **기능** | SessionStart 시 KST 경로 / trail 파일 목록 / positions / portfolio 컨텍스트 주입 |
| **신규 구현** | `infrastructure/_common/bootstrap_context.py` — `get_bootstrap_context()` 함수 + CLI `python -m infrastructure._common.bootstrap_context` |

### 사용 방법

```bash
# CLI (cron pipeline 등)
python -m infrastructure._common.bootstrap_context --date 2026-06-10

# Python import
from infrastructure._common.bootstrap_context import get_bootstrap_context
context = get_bootstrap_context("2026-06-10")
```

`run_daily_local.sh` 의 Phase 0a (drift_audit start) 직후에 호출되어
context 를 stdout 으로 출력. Zed Agent 의 context injection 은 수동
`AGENTS.md` 참조 또는 interactive session 에서 직접 호출.

---

## 미구현으로 파기된 Hook (기록 보존)

| # | 제안 Hook | 역할 | 비고 |
|---|---|---|---|
| — | `pre_no_autotrade` | KIS order 등 매매 호출 차단 | `.claude/settings.json` 의 `permissions.deny` + `runtime-policy.yaml` + 코드 레벨 타입 안전성(G9) 3중 방어 존재. 구현 불필요. |
| — | `post_redact_secrets` | API key 패턴 발견 시 reject | chmod 0600 + `.gitignore` + `load_env_file()` 만 사용. |
| — | `post_forbidden_language` | "should buy/sell" 등 차단 | 정적 문서 + 인간 리뷰 신뢰. |
| — | `post_falsifier_validator` | vague falsifier 검증 | Stage 4 skill 자체에 검증 로직 내장. |
| — | `post_asymmetry_validator` | downside_floor 누락 시 reject | Stage 4 skill 자체에 검증 로직 내장. |
| — | `stop_sample_gate` | alpha claim sample size 검증 | 정적 `thresholds.yaml` + 인간 리뷰. |

---

## 영향 요약

| 관점 | 전 (Claude Code) | 후 (Zed) |
|---|---|---|
| **실시간 enforcement** | Hook 이 모든 Write/Edit/Bash 실시간 차단 | Pre-commit + CI + 정적 문서 |
| **컨텍스트 주입** | UserPromptSubmit+SessionStart 자동 | `AGENTS.md` 정적 + `bootstrap_context.py` 수동 |
| **보안** | PreToolUse 에서 `.env` 접근 강제 차단 | chmod 0600 + 코드 룰 |
| **품질 게이트** | PostToolUse citation + lint 자동 검증 | Pre-commit / CI / 수동 리뷰 |
