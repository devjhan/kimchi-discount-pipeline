#!/usr/bin/env bash
# .claude/hooks/quality/brief_citation_gate/entrypoint.sh
# ----------------------------------------------------------------------------
# PostToolUse(Write|Edit) 와 Stop 양쪽에서 호출.
# tool_input.file_path 가 daily-brief.md 로 끝날 때만 fire (short-circuit
# 은 Python 본체에서 수행).
#
# stdin (Claude Code):
#   {"tool_name": "Write"|"Edit", "tool_input": {...}, ...}
#   Stop 에서는 tool_input 비어있을 수 있음 → $TRAIL_TODAY/daily-brief.md fallback.
#
# stdout:
#   block 시: hookSpecificOutput JSON 또는 {"decision":"block","reason":...}
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

python3 "$SCRIPT_DIR/validator.py" "$@"
