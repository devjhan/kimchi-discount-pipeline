#!/usr/bin/env bash
# .claude/hooks/quality/lint_directives/entrypoint.sh
# ----------------------------------------------------------------------------
# PostToolUse hook (matcher: Write|Edit). Write/Edit 직후 작성된 파일을 read 해
# directive lint 실행. M1 (현재) 은 dry-run 모드 — $AUDIT_DIR/_hook_audit.log
# 에 finding 만 기록하고 차단/inject 안 함. M2 에서 enforce 모드로 flip 가능.
#
# 환경변수:
#   INVEST_DIRECTIVE_LINT_MODE=dry-run (default) | warn | enforce
#     - dry-run:  audit log 만, exit 0
#     - warn:     hookSpecificOutput.additionalContext 로 violation list inject (재시도 유도)
#     - enforce:  decision=block (M2 활성)
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
