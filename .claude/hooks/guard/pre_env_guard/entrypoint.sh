#!/usr/bin/env bash
# .claude/hooks/guard/pre_env_guard/entrypoint.sh
# ----------------------------------------------------------------------------
# PreToolUse hook (matcher: Read|Bash|Write|Edit).
# .env (secret dotenv) 에 대한 모든 직접 접근을 차단한다 (.env.example/.template 는 허용).
#
# stdin (Claude Code):
#   {"tool_name": "Read"|"Bash"|"Write"|"Edit", "tool_input": {...}, ...}
# stdout:
#   block 시: hookSpecificOutput JSON (permissionDecision=deny)
#   허용 시: empty
# ----------------------------------------------------------------------------

set -uo pipefail

if [ -n "${BASH_SOURCE+x}" ] && [ -n "$BASH_SOURCE" ]; then
    CURRENT_SCRIPT="${BASH_SOURCE[0]}"
else
    CURRENT_SCRIPT="$0"
fi
SCRIPT_DIR="$(cd "$(dirname "$CURRENT_SCRIPT")" && pwd)"
INVEST_ROOT="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null || true)"
if [ -z "$INVEST_ROOT" ]; then
    INVEST_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
fi

export INVEST_ROOT
INVEST_HOOK_INPUT="$(cat)"
export INVEST_HOOK_INPUT

python3 "$SCRIPT_DIR/validator.py"
