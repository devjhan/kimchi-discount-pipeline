# D-SH — Shell Hook 작성 컨벤션

`$HOOKS_DIR/**/entrypoint.sh` 및 `$OPERATIONS_DIR/cron/*.sh` 의 모든 shell 스크립트가 따라야 할 작성 컨벤션. `inject_session_state/entrypoint.sh` / `inject_investment_contract/entrypoint.sh` / `brief_citation_gate/entrypoint.sh` 가 모범.

---

## D-SH-1 — shebang + `set -uo pipefail` 강제 (헤더 3 줄 내)

**근거**: 미정의 변수 / 파이프 중간 실패가 silently 통과하면 hook 이 "통과한 척" 하다 보안가드를 우회. 새 hook 작성 시 첫 5 줄 안에 둘 다 들어가야 한다.

❌ 금지
```bash
#!/usr/bin/env bash
# (set 호출 없음)
SOME_VAR="$1"
exec python3 some.py
```

✅ 올바름
```bash
#!/usr/bin/env bash
# .claude/hooks/foo_bar.sh — foo bar guard.
set -uo pipefail
```

`set -e` 는 의도적으로 빼는 경우가 있음 — Python wrapper 가 exit code 로 통신. 그러나 `-u` (undefined var) + `-o pipefail` 은 필수.

**Hook**: `block_anti_patterns.sh` (PreToolUse) — 새 `.sh` 파일 헤더 5 줄 내 `set -uo pipefail` (또는 `set -euo pipefail`) 부재 시 exit 2.

---

## D-SH-2 — stdin → env var 패턴 (`INVEST_HOOK_INPUT`)

**근거**: Claude Code 가 stdin 으로 hook JSON payload 를 전달. shell 은 JSON parsing 약함 → stdin 을 env var 로 옮기고 Python helper 가 처리. `inject_investment_contract.sh` 패턴 직역.

✅ 올바름
```bash
INVEST_HOOK_INPUT="$(cat)"
export INVEST_HOOK_INPUT
python3 "$SCRIPT_DIR/_foo_bar.py"
```

❌ 금지
```bash
cat | jq -r '.tool_input.file_path'   # jq 부재 환경 / JSON 변형에 약함
read PAYLOAD                          # 첫 줄만 읽힘
```

**Hook**: `inject_only` (PR 리뷰 시 인용).

---

## D-SH-3 — stderr 출력 한국어 1~3 줄

**근거**: hook 의 stderr 는 사용자 + 에이전트 모두에게 표시되는 deny 사유. 너무 짧으면(`block`) action 불가능, 너무 길면(50 줄) 가독성 0. 한국어 1~3 줄 + 실행가능한 대안 + 우회 방법(legacy-ok / env override) 필수.

✅ 표준 출력 (직역 패턴 — `_brief_citation_gate.py` 라인 231~240):
```
[hook-name] {N} violation(s) in {file}.
{D-ID} 위반: {짧은 설명}
  - L{ln}: {찾은 코드} — Fix: {1줄 가이드}
참조: $DIRECTIVES_DIR/{file}#{anchor}
```

❌ 금지
```
ERROR
```

```
Traceback (most recent call last):
  File "...", line 42, in <module>
    ...   # 50줄 traceback 노출 (실제 deny 사유 묻힘)
```

**Hook**: `lint_directives.sh` (PostToolUse, M2) — `.sh` 파일 안 `>&2` 출력 라인 wc 로 길이 검사.

---

## D-SH-4 — telemetry `$AUDIT_DIR/_hook_audit.log` append 의무

**근거**: hook 모두가 자기 실행을 기록해야 사후에 false positive / false negative 추적 가능. 형식 표준화 — `{iso_kst}\t{hook_name}\t{decision}\t{reason}`.

✅ 표준 패턴 (Python wrapper 안)
```python
def _audit_log(decision: str, reason: str) -> None:
    try:
        audit_dir = Path(os.environ["AUDIT_DIR"])
        audit_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(KST).isoformat(timespec="seconds")
        with (audit_dir / "_hook_audit.log").open("a", encoding="utf-8") as f:
            f.write(f"{ts}\t{HOOK_NAME}\t{decision}\t{reason}\n")
    except Exception:
        pass   # audit log 실패는 hook 의사결정에 영향 안 줌
```

ALLOW / BLOCK / STOP_BLOCK / WARN 4 종 decision 만 사용.

**Hook**: `inject_only` — 본 룰은 hook 자체의 자기 검사 (작성 시 review).

---

## D-SH-5 — 경로는 env var 우선, 없으면 `$INVEST_ROOT` 기준 (path literal 최소화)

**근거**: 중앙 alias export (구 `resolve_aliases`) 는 제거됐다. hook entrypoint 는 git toplevel 을 `$INVEST_ROOT` 로 export 하므로, 이미 set 된 env var (`$AUDIT_DIR` / `$TRAIL_TODAY` 등) 를 우선 쓰고 없으면 `$INVEST_ROOT` 기준으로 계산한다.

✅ 올바름
```bash
audit_dir="${AUDIT_DIR:-$INVEST_ROOT/telemetry/audit}"
```

❌ 금지
```bash
audit_dir="$INVEST_ROOT/telemetry/audit"   # path literal
```

**Hook**: `block_path_literals.sh` (PreToolUse, 기존).

---

## D-SH-6 — `INVEST_ROOT` 해소 표준 패턴

**근거**: hook 이 git 외 환경(cron / CI)에서도 실행될 수 있음. `git rev-parse` 실패 fallback 으로 `BASH_SOURCE` 기반 상대경로 해소.

✅ 표준 패턴 (`inject_investment_contract.sh` 라인 22~31 직역)
```bash
if [ -n "${BASH_SOURCE+x}" ] && [ -n "$BASH_SOURCE" ]; then
    CURRENT_SCRIPT="${BASH_SOURCE[0]}"
else
    CURRENT_SCRIPT="$0"
fi
SCRIPT_DIR="$(cd "$(dirname "$CURRENT_SCRIPT")" && pwd)"
INVEST_ROOT="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null || true)"
if [ -z "$INVEST_ROOT" ]; then
    INVEST_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
fi
export INVEST_ROOT
```

**Hook**: `inject_only`.
