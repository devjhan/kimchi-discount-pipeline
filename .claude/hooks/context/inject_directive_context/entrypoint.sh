#!/usr/bin/env bash
# .claude/hooks/context/inject_directive_context/entrypoint.sh
# ----------------------------------------------------------------------------
# UserPromptSubmit hook. 사용자 prompt 와 첨부 파일 확장자를 보고 관련 directive
# 본문을 hookSpecificOutput.additionalContext 로 동적 주입.
#
# 매칭 로직 (_inject_directive_context.py 참조):
#   - prompt 가 "코드/구현/작성/fix/Write/Edit" 등 키워드 매칭 → 00-principles 항상
#   - 매칭 파일 확장자 (.py/.sh/.yaml/.json/.md) 별로 해당 D-LANG directive 본문
#   - 매칭 없으면 빈 객체 {} 출력 (zero overhead)
#
# stdin: Claude Code JSON payload
# stdout: { "hookSpecificOutput": { ... } } 또는 {}
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
