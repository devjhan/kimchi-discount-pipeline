#!/usr/bin/env bash
# .claude/hooks/context/inject_investment_contract/entrypoint.sh
# ----------------------------------------------------------------------------
# UserPromptSubmit hook. 사용자 프롬프트가 investment skill trigger 와 매치
# 하면 _shared/investment/bootstrap.md 의 cross-cutting 섹션을
# hookSpecificOutput.additionalContext 로 inject.
# 이로써 SKILL.md 가 Reference Contract 의 read 명령을 잊어도 contract 가
# 시스템 컨텍스트에 들어와 있다.
#
# stdin (Claude Code 가 전달):
#   { "prompt": "...", "session_id": "...", ... }
# stdout:
#   { "hookSpecificOutput": {
#       "hookEventName": "UserPromptSubmit",
#       "additionalContext": "..."
#   } }
# 비매치 시: 빈 객체 stdout (Claude Code 는 inject 안 함).
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

# stdin (Claude Code JSON payload) 를 env var 로 전달.
# (heredoc 안 변수 치환은 newline 보존 문제로 사용하지 않음.)
INVEST_HOOK_INPUT="$(cat)"
export INVEST_HOOK_INPUT

python3 "$SCRIPT_DIR/validator.py"
