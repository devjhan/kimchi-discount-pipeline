#!/usr/bin/env bash
# .claude/hooks/bootstrap/inject_session_state/entrypoint.sh
# ----------------------------------------------------------------------------
# SessionStart hook — 세션 시작 시 오늘 KST 컨텍스트를 주입.
#
# 경로는 validator.py 가 REPO_ROOT 기준 literal 로 직접 계산 (topology 미경유).
# 본 hook 은 validator.py 를 호출해 다음 4항목을 plain text 로
# stdout 출력 → Claude Code 가 system-reminder 로 표시:
#
#   1. 주요 경로 (오늘 KST trail / audit / positions / user_context)
#   2. 오늘 trail 파일 목록
#   3. 보유 포지션 현황
#   4. 포트폴리오 컨텍스트 (portfolio.local.yaml)
#
# exit code: 항상 0 (warn-only) — 실패해도 세션 차단 안 함.
# ----------------------------------------------------------------------------

set -uo pipefail

if [ -n "${BASH_SOURCE+x}" ] && [ -n "$BASH_SOURCE" ]; then
    CURRENT_SCRIPT="${BASH_SOURCE[0]}"
else
    CURRENT_SCRIPT="$0"
fi
SCRIPT_DIR="$(cd "$(dirname "$CURRENT_SCRIPT")" && pwd)"
ROOT="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null || true)"
if [ -z "$ROOT" ]; then
    ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
fi

export INVEST_ROOT="$ROOT"

python3 "$SCRIPT_DIR/validator.py" || true

exit 0
