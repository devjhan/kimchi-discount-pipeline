# .claude/hooks/ — Hard Guard skeleton

본 디렉토리는 investment_v3 의 **defensive architecture** 를 떠받치는 PreToolUse / PostToolUse / Stop / SessionStart hook 들의 위치이다. **에이전트가 hard guard 를 우회하면 시스템 1원칙(생존)이 무너진다**.

> **[2026-06-02] path-SSoT 머신러리 제거.** `topology.yaml` + `from_alias` +
> `resolve_aliases` hook + `doctrine_lint.py` + `skill_lint_session` hook +
> `block_deprecated_terms` hook + `skill-registry.yaml` / `deprecated-references.yaml` /
> `deprecated-artifacts.yaml` 이 모두 삭제됐다. 경로는 `infrastructure/_common/utils.py`
> 의 path helper 가 직접 계산한다. **아래 본문 중 위 항목을 ✅ 로 기술한 옛 섹션은
> 역사적 설계 노트이며 더 이상 유효하지 않다** (`resolve_aliases.sh — SessionStart
> resolver` / SSoT layer spec 등).

현재 활성 hook (`.claude/settings.json`):
- ✅ `bootstrap/inject_session_state/` (SessionStart) — 오늘 KST 주요 경로(REPO_ROOT 기준 literal) + trail 파일 목록 + 보유 포지션 + portfolio 컨텍스트를 plain text 로 주입.
- ✅ `context/inject_investment_contract/` (UserPromptSubmit) — investment trigger 매치 시 `bootstrap.md` §1/§3/§5/§7 을 `hookSpecificOutput.additionalContext` 로 주입.
- ✅ `context/inject_directive_context/` (UserPromptSubmit) — 파일 확장자/키워드 매칭 시 `governance/directives/` 의 directive 본문 주입.
- ✅ `context/inject_guidelines/` (UserPromptSubmit) — hard-guards 관련 룰 주입.
- ✅ `guard/pre_env_guard/` (PreToolUse Read/Bash/Write/Edit) — `.env` 직접 접근 차단.
- ✅ `guard/block_anti_patterns/` (PreToolUse Write/Edit) — D-PY-1 / D-SH-1 / D-CFG-1 / D-SEC-1 anti-pattern 즉시 차단. stderr 에 D-ID + Fix + 우회 env (`INVEST_DIRECTIVE_GUARD_OFF=1` / `INVEST_SEC_GUARD_OFF=1`).
- ✅ `quality/brief_citation_gate/` (PostToolUse Write/Edit + Stop) — brief 숫자 citation 의무 검사.
- ✅ `quality/lint_directives/` (PostToolUse Write/Edit) — D-PY-2/3/5 / D-CFG-2/3 검사 (M1 dry-run).
- ❌ defensive guard 본체 일부 (pre_no_autotrade / post_redact_secrets 등) — **사용자 후속 작업**.

---

## 가드 매핑 (작성 시 우선순위 순)

### 우선순위 High (안전결정적, fail-closed by default)

| # | 가드 | hook event | matcher | 제안 파일명 | 역할 |
|---|---|---|---|---|---|
| 1 | auto-trade 차단 | PreToolUse | Bash | `pre_no_autotrade.py` | KIS order 등 매매 호출 정규식 차단 (`kis_order`, `place_order`, `submit_buy_*`). settings.json 의 `permissions.deny` 도 1차 방어선. |
| 2 | path guard | PreToolUse | Write,Edit | `pre_path_guard.py` | Write 대상이 `$TRAIL_TODAY/`, `governance/specs/`, `governance/procedures/` 외 영역이면 reject. `governance/AXIOMS/` 와 `governance/topology.yaml` 은 read-only (변경하려면 사용자 명시 승인 PR). |
| 3 | secret leak | PostToolUse | Bash,Write,Edit | `post_redact_secrets.py` | DART_API_KEY / KIS_APP_SECRET / KIS_ACCOUNT_NUMBER / TELEGRAM_BOT_TOKEN 패턴 매칭. 발견 시 reject + redacted log → `telemetry/logs/_hook_audit.log`. |

### 우선순위 Medium (semantic, audit-only burn-in 후 enforce)

| # | 가드 | hook event | matcher | 제안 파일명 | 역할 |
|---|---|---|---|---|---|
| 4 | alias 우회 검출 | PostToolUse | Write,Edit | `post_alias_compliance.py` | 산출물에 path string literal (`operations/2026-`, `governance/AXIOMS`, `.handoff/` 등) 발견 시 reject — alias env var 만 사용해야 한다는 SSOT 룰 강제. |
| 5 | forbidden language | PostToolUse | Write,Edit | `post_forbidden_language.py` | "should buy/sell", "guaranteed", "no-brainer", "alpha confirmed" 등 (`$SPECS_DIR/hard-guards.md` Section 3) 매칭 시 reject. |
| 6 | vague falsifier | PostToolUse | Write `04-thesis-candidates.json` | `post_falsifier_validator.py` | thesis.falsifier 가 (time-cap / metric-trigger / event-trigger) 카테고리에 속한 구체 표현인지 검증. vague pattern (실적 안 좋으면 / thesis 깨지면 / 전망 나빠지면) reject. |
| 7 | downside_floor / asymmetry_ratio | PostToolUse | Write `04-thesis-candidates.json` | `post_asymmetry_validator.py` | downside_floor 누락 시 reject. asymmetry_ratio < 2 면 reject 또는 size-half cap 권고. |

### 우선순위 Low (브리프 산출 직후, audit-only 권장)

| # | 가드 | hook event | matcher | 제안 파일명 | 역할 |
|---|---|---|---|---|---|
| 8 | sample size gate | Stop | (브리프) | `stop_sample_gate.py` | brief 본문에 N<10 + alpha claim, N<100 + strategy proven 등 위반 패턴 검사. |
| 9 | citation gate | Stop | (브리프) | `stop_citation_gate.py` | brief 안 모든 숫자가 `Source@ts=value` 형태 인용 동반하는지 검증. |

---

## SessionStart 컨텍스트 주입 — 완료 및 추후 후보

### 완료 (`inject_session_state.sh` — SessionStart phase 3)

`_inject_session_state.py` 가 다음 4항목을 plain text stdout → system-reminder 로 주입:

| 항목 | 내용 | 비고 |
|---|---|---|
| Alias → 실제 경로 매핑 | topology.yaml 전체 alias (37개), KST date 치환 포함 | `resolve_aliases.sh` 의 shell-only export 를 Claude 컨텍스트에 보완 |
| $TRAIL_TODAY 파일 목록 | 오늘 trail 디렉토리 파일명 + byte 수 | 어떤 stage 산출물이 존재하는지 즉시 파악 |
| 보유 포지션 현황 | `$POSITIONS_DIR/*.yaml` (없으면 "없음" 한 줄) | ticker / status / falsifier_proximity.band 요약 |
| 포트폴리오 컨텍스트 | `portfolio.local.yaml` → `portfolio.yaml` fallback | total_capital / drawdown / cash / volatility_tolerance |

### 추후 후보 (Middle ROI — `inject_session_state.sh` 확장 또는 별도 hook)

현재 커버되지 않는 항목. 운영 경험 쌓인 뒤 필요도 검증 후 추가.

| 우선순위 | 항목 | 내용 | 트리거 조건 | 구현 방식 |
|---|---|---|---|---|
| ★★ | macro regime 요약 | `$TRAIL_TODAY/00-macro-regime.json` 의 `regime` label + `cash_band` | trail 파일 존재 시 | `_inject_session_state.py` 내 섹션 추가 |
| ★★ | behavior.local.yaml | `yahoo_fallback` 등 runtime switch 전체 | 파일 존재 시 | `_inject_session_state.py` 내 섹션 추가 |
| ★ | 최신 cron-log tail | `telemetry/logs/cron/` 최신 `.log` 파일 마지막 20줄 | 오늘 log 존재 시 | `_inject_session_state.py` 내 섹션 추가 |
| ★ | shadow-portfolio-state | `$AUDIT_DIR/shadow-portfolio-state.json` 4-tier 누적 수익률 요약 | 파일 존재 시 | `_inject_session_state.py` 내 섹션 추가 |

> **확장 방법**: `_inject_session_state.py` 하단에 섹션 블록 추가 후 `out` 리스트에 append. 각 섹션은 파일 존재 여부 guard + try/except 로 wrap — 실패 시 warn 한 줄만 출력.

---

## Hook 표준 spec

모든 hook 은 다음 규약을 따른다 (이 룰을 따르면 settings.json 의 슬롯에 entry 만 append 하면 즉시 동작):

### Stdin
- Claude Code 가 hook 호출 시점의 컨텍스트 JSON 을 stdin 으로 전달.
- PreToolUse: `{"tool_name": "Bash"|"Write"|"Edit", "tool_input": {...}}`
- PostToolUse: `{"tool_name": ..., "tool_input": ..., "tool_output": ...}`
- Stop: `{"transcript": [...], ...}` — 최종 산출물 컨텍스트 포함.
- 스크립트 시작에 `data = json.load(sys.stdin)` 권장.

### Stdout
- 일반적으로 사용 안 함. 디버그 정보가 필요하면 `>&2` 로 stderr 사용.

### Stderr
- reject 사유 메시지. 사용자 / 에이전트가 읽을 수 있는 한국어 1~3 줄.

### Exit code
- `0` — allow (hook 정상 통과).
- `2` — reject (Claude Code 가 도구 호출 차단).
- 기타 — Claude Code 가 hook 자체 에러로 처리.

### 모드
- 안전결정적 가드 (1, 2, 3) — 처음부터 fail-closed (exit 2 reject).
- 의미 가드 (4, 5, 6, 7, 8, 9) — `--audit-only` 환경변수 지원:
  - `HOOK_AUDIT_ONLY=1` 이면 violation 발생 시 `telemetry/logs/_hook_audit.log` 에 append 만 하고 exit 0.
  - 1~2 주 burn-in 후 사용자가 본인 판단으로 enforce 모드로 flip.

### Path 룰
- Hook 은 `INVEST_ROOT` env (entrypoint 가 git toplevel 로 export) 기준으로 경로를 계산하거나,
  도메인 코드 재사용이 필요하면 `infrastructure/_common/utils.py` 의 path helper 를 import 한다.
  ```python
  import os
  from pathlib import Path
  root = Path(os.environ["INVEST_ROOT"])
  axioms = root / "governance" / "AXIOMS"
  # 또는 도메인 helper 재사용:
  # from infrastructure._common.utils import audit_dir; audit_dir()
  ```
- `$TRAIL_TODAY` / `$AUDIT_DIR` 같은 env var 가 set 이면 helper 가 우선 사용 (테스트/cron override).

### Telemetry
- 모든 hook 은 fire 시점에 `telemetry/logs/_hook_audit.log` 에 한 줄 append:
  ```
  {iso_kst}\t{hook_name}\t{decision}\t{reason}
  ```
  audit-only / enforce 모드 모두 동일.

---

## resolve_aliases.sh — SessionStart resolver

이 hook 은 다른 hook 들이 의존하는 alias env var 를 SessionStart 시점에 한 번 export 하는 backbone. Phase 4 어시스턴트는 1단계 (sanity check) 까지만 작성. 2단계 (실제 alias export) 는 사용자 본인이 채운다.

### 작성 가이드

```bash
# (a) 오늘 / 전영업일 (KST)
DATE="$(TZ=Asia/Seoul date +%Y-%m-%d)"
DOW="$(TZ=Asia/Seoul date +%u)"   # 1=Mon ... 7=Sun
case "$DOW" in
  6) DATE_TODAY="$(TZ=Asia/Seoul date -v -1d +%Y-%m-%d)" ;;
  7) DATE_TODAY="$(TZ=Asia/Seoul date -v -2d +%Y-%m-%d)" ;;
  *) DATE_TODAY="$DATE" ;;
esac
DATE_YEST="$(TZ=Asia/Seoul date -v -1d +%Y-%m-%d)"   # 주말 보정 추가 권장

# (b) topology.yaml 파싱 — bash 만으로 까다로우면 python3 위임:
python3 - <<EOF
import os, yaml
from pathlib import Path
ROOT = Path("$ROOT")
topo = yaml.safe_load((ROOT/"governance/topology.yaml").read_text())
paths   = topo["paths"]
aliases = topo["aliases"]
for env_name, key in aliases.items():
    rel = paths[key].replace("{date}", "$DATE_TODAY").replace("{date_yesterday}", "$DATE_YEST")
    print(f"export {env_name}={ROOT}/{rel}")
EOF | source /dev/stdin
```

→ 본 README 를 그대로 복사해 `resolve_aliases.sh` 의 `# TODO(user)` 자리에 붙여넣고 입맛에 맞게 수정.

---

## 작성 체크리스트 (사용자가 점진적으로 채움)

### SSoT layer (Skills Migration — 완료)

- [x] resolve_aliases.sh 2단계 본문 (alias export)
- [x] skill_lint_session.sh (SessionStart drift 검증)
- [x] inject_investment_contract.sh (UserPromptSubmit contract inject)
- [x] block_deprecated_terms.sh (PreToolUse rename 차단)
- [x] inject_session_state.sh (SessionStart alias 매핑·trail 목록·포지션·portfolio 컨텍스트 주입)

### Coding Directives layer (Phase 8 — 완료)

- [x] inject_directive_context.sh (UserPromptSubmit directive 본문 inject)
- [x] block_anti_patterns.sh (PreToolUse D-PY-1/D-SH-1/D-CFG-1/D-SEC-1 차단)
- [x] lint_directives.sh (PostToolUse D-PY-2/3/5 + D-CFG-2/3 검사, M1 dry-run)
- [x] doctrine_lint check #15~18 (D-ID 형식 / 유일성 / README 일관 / hook reference 일관)

### Defensive guard layer (사용자 후속 작업)

- [ ] pre_no_autotrade.py
- [x] pre_path_guard.py — `block_path_literals.sh` / `_block_path_literals.py` 로 구현 (doctrine 본문의 raw path literal 차단, alias 강제)
- [x] pre_env_guard.py — .env 직접 접근(Read/Bash/Write/Edit) 차단
- [x] stop_citation_gate.py — `brief_citation_gate.sh` / `_brief_citation_gate.py` 로 구현 (PostToolUse Write/Edit + Stop hook 양쪽 active). brief 본문의 숫자 evidence 누락 검출.
- [ ] post_redact_secrets.py
- [ ] post_alias_compliance.py
- [ ] post_forbidden_language.py
- [ ] post_falsifier_validator.py
- [ ] post_asymmetry_validator.py
- [ ] stop_sample_gate.py

---

## SSoT layer hook spec (완료된 4개)

### `resolve_aliases.sh` (SessionStart, phase 1)

`governance/topology.yaml` 의 `aliases:` block 을 read 해 모든 alias 를 환경변수로 export. KST date 정규화 (`{date}` / `{date_yesterday}` placeholder 치환) 포함. 새 alias 가 topology.yaml 에 추가되면 자동 export — 본 hook 수정 불필요.

### `skill_lint_session.sh` (SessionStart, phase 2)

`infrastructure/_common/doctrine_lint.py` 호출. 14개 검증 항목:
1-9 (Layer 3): alias resolution / threshold path / G-rule ID / artifact DAG / skill name match / bootstrap dedup / path literal
10-14 (Layer 5): rename literal / G-ID range / schema name / 등 (deprecated-references.yaml 부재 시 일부 skip)

stdout 출력 형식:
- `[doctrine-lint] OK aliases=N g_rules=N skills=N artifacts=N files=N` + `[doctrine-lint] OK no findings.`
- 또는 `[doctrine-lint] FOUND N issues:` + 각 finding `<file:line> <code> <detail>`

CLI 직접 실행 (디버그):
```bash
python3 infrastructure/_common/doctrine_lint.py            # warn-only
python3 infrastructure/_common/doctrine_lint.py --strict   # finding>0 시 exit 1
python3 infrastructure/_common/doctrine_lint.py --quiet    # OK 시 출력 생략
```

### `inject_investment_contract.sh` (UserPromptSubmit)

사용자 prompt 가 investment skill trigger 매치 (`/investment-stage*-*` 슬래시 / `thesis` 등 키워드 / `$TRAIL_TODAY` 등 alias 인용) 시:
- `_shared/investment/bootstrap.md` 의 §1 / §3 / §5 / §7 발췌
- `governance/skill-registry.yaml` 의 `guard_letter_to_id` + 매치 skill 의 entry (inputs / outputs / applicable_guards / applicable_axioms)
- 위 둘을 합쳐 `hookSpecificOutput.additionalContext` 로 출력 → Claude Code 가 시스템 컨텍스트에 prepend.

비매치 시 빈 객체 `{}` 출력 (inject 안 함). 비-investment 세션 토큰 낭비 0.

본체는 `_inject_investment_contract.py` (sibling python script). shell wrapper 는 stdin → env var 전달만 담당.

### `block_deprecated_terms.sh` (PreToolUse, matcher: Write / Edit)

doctrine 영역 (`governance/`, `.claude/skills/`, `AGENTS.md`, `CLAUDE.md`, `domains/**/*.py`) 에 대한 Write / Edit 호출을 가로채:
- tool_input 의 `new_string` (Edit) 또는 `content` (Write) 를 `deprecated-references.yaml` 의 `from:` 문자열과 substring 매치
- 매치 + 의도적 legacy fence (`<!-- legacy-ok -->`) 밖이면 block + reason 안내
- 매치 없으면 통과 (exit 0)

Phase 7 cleanup 으로 잔류 macro_config 인용을 일소한 후 활성화 — 새 도입만 차단하는 fail-forward 메커니즘.

### `block_path_literals.sh` (PreToolUse, matcher: Write / Edit)

doctrine 본문에 raw path literal 의 새 도입을 차단. 본체는 `_block_path_literals.py`.

<!-- legacy-ok -->
**검사 대상 파일**:
- 모든 `*.md` (governance/, .claude/skills/, AGENTS.md, CLAUDE.md, README.md ...)
- prefix-제한 `*.yaml`/`*.yml`: `.claude/skills/`, `governance/specs/`, `governance/AXIOMS/`, `governance/procedures/`

**차단 정규식 두 종**:
- 절대경로 — `/(Users|opt|var|etc|tmp|home|private|usr/local)/...` (shebang `#!/...` 통과)
- 상대경로 — `(governance|operations|infrastructure|domains|.claude/skills|.claude/hooks)/...` (`$ALIAS/...` 통과)

**Self-exclude** (검사 제외):
- `governance/topology.yaml` (alias→path SSoT), `deprecated-references.yaml`, `skill-registry.yaml`, `runtime-policy.yaml` (+ `.local`, `.example`), `thresholds.yaml`
- `.gitignore`, `.gitattributes`, `.claude/settings.json`, `.claude/settings.local.json`
- 모든 `.py` / `.sh` / `.json` / `.toml` / `.lock` / `.cfg` / `.ini`

**우회 메커니즘**:
- `<!-- legacy-ok -->...<!-- /legacy-ok -->` fence — 의도적 historical 인용
- 코드 fence ` ``` ... ``` ` — 예시 코드
- HTML 주석 — 메타 정보
- `$ALIAS_DIR/path` 표기 — alias 정규식 lookbehind 통과
- `INVEST_PATH_GUARD_OFF=1` 환경변수 — 일시적 전역 toggle

**출력**: block 시 `hookSpecificOutput` JSON (`permissionDecision: "deny"`) + 에러 메시지에 line 번호 + 매치된 substring + 권장 alias hint.

doctrine_lint `check_path_literals` (SessionStart warn-only, `.claude/skills/**/*.md` 한정) 의 갭 셋 (절대경로 / skill 바깥 doctrine / 실시간 차단) 을 메우는 layer.
<!-- /legacy-ok -->

각 hook 작성 후 `.claude/settings.json` 의 해당 슬롯 (PreToolUse / PostToolUse / Stop) 에 entry 추가. 추가 즉시 활성화.
