#!/usr/bin/env bash
set -uo pipefail
# .claude/hooks/context/inject_guidelines/entrypoint.sh
# UserPromptSubmit hook — prompt 의 path 후보 상위 .guidelines/*.md 자동 inject.
# 매칭 없으면 빈 객체 {} (zero overhead). stdin: Claude Code JSON payload.

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
