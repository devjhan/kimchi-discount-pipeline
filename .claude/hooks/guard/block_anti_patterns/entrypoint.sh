#!/usr/bin/env bash
# .claude/hooks/guard/block_anti_patterns/entrypoint.sh
# ----------------------------------------------------------------------------
# PreToolUse hook (matcher: Write|Edit). 작성하려는 content 에 신뢰도 높은
# anti-pattern 이 있으면 exit 2 로 차단 + stderr 에 D-ID 인용 + Fix 가이드.
#
# 검사 대상 (M1):
#   - D-PY-1  새 .py 파일에 from __future__ import annotations 부재
#   - D-SH-1  새 .sh 파일에 set -uo pipefail 부재
#   - D-CFG-1 새 governance/*.yaml 에 version: / description: 헤더 부재
#   - D-SEC-1 content 본문 secret-like literal 매립
#
# 우회: INVEST_DIRECTIVE_GUARD_OFF=1 (전역) / INVEST_SEC_GUARD_OFF=1 (D-SEC-1 만)
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
