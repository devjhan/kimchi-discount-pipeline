#!/usr/bin/env bash
set -uo pipefail
# ============================================================
# applications/run_daily_local.sh — launchd 진입점 (primary deployment)
# ============================================================
#
# governance/specs/deployment-residency.md §2 primary 의 단일 wrapper.
# launchd LaunchAgent (com.investment_v3.daily_pipeline) 가 매일 07:30 KST 호출.
# 기존 cloud routine 의 cloud_routine_run.sh 는 deprecated — 본 wrapper 가
# 한국 residential IP 환경에서 KIS/DART/KRX 통과를 보장한다.
#
# 책임:
#   0a. drift_audit start snapshot — scheduler-state 기록
#   0b. PID 락 — 전일 실행이 24h 넘게 미종료된 경우 새 run skip
#   0c. 네트워크 readiness poll (최대 60s) — wake 직후 WiFi 안정화 대기
#   0d. venv python 검증 (없으면 자동 bootstrap)
#   0e. alias env 로드 (TZ / TRAIL_TODAY 등)
#
#   1. pre-stage4 (Stage 0~3 결정적)
#   2. Stage 4 LLM (`claude -p /investment-stage4-thesis-auditor $DATE`)
#   3. post-stage4 (Stage 5~5d 결정적)
#   4. Stage 6 LLM (`claude -p /investment-stage6-brief-author $DATE`)
#   5. Notify manifest 작성 (python -m infrastructure.notify.dispatcher)
#   6. MCP 알림 발송 (`claude -p <dispatch_manifest_prompt>` + slack/gmail MCP)
#   7. audit shadow-portfolio (python -m domains.audit_integrity.main — 결정론, F-6)
#
#   8. drift_audit end snapshot
#
# Hard guards:
#   - 한 stage 실패해도 다음 stage 시도 (graceful degrade) — daily_pipeline.sh 와 동일
#   - PID 락 잔존 시 익일 새 run 즉시 skip — 중복 방지
#   - 어떤 stage 도 매매 명령 실행 없음 (G9) — read/research 전용 chain
#
# 호출:
#   bash applications/run_daily_local.sh                # 오늘 (KST)
#   bash applications/run_daily_local.sh --date 2026-05-13
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

export REPO_ROOT
export TZ="${TZ:-Asia/Seoul}"

# MCP tool full names — server UUID 로 namespaced. 5/14 incident 후 short name
# (mcp__slack_send_message / mcp__create_draft) 가 --allowed-tools 와 매칭 실패해
# 헤드리스 dispatch 에서 권한 dialog 로 전환 → 송신 0건 발생. MCP 서버 재등록
# 시 본 UUID 갱신 필요 (.claude/settings.json permissions.allow 도 동일 값 유지).
SLACK_MCP_TOOL="mcp__bb9a3bd8-7422-48cc-8787-8ff8cc5441bf__slack_send_message"
GMAIL_MCP_TOOL="mcp__d49a4519-3341-4883-9786-dc2e0e2aae3e__create_draft"

# CLI flag
DATE_OVERRIDE=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --date)   DATE_OVERRIDE="$2"; shift 2 ;;
    --date=*) DATE_OVERRIDE="${1#--date=}"; shift ;;
    *)        echo "[run_daily_local] unknown arg: $1" >&2; exit 2 ;;
  esac
done

LOG_DIR="$REPO_ROOT/telemetry/logs/launchd"
mkdir -p "$LOG_DIR"

LOCK_FILE="/tmp/investment_v3.daily_pipeline.pid"
ts() { date '+%Y-%m-%dT%H:%M:%S%z'; }

echo "============================================================"
echo "[run_daily_local] $(ts) starting"

# 0a. drift_audit start
PYTHON_ENV="$REPO_ROOT/infrastructure/_common/python_env.sh"
if [ -f "$PYTHON_ENV" ]; then
  # shellcheck source=/dev/null
  source "$PYTHON_ENV"
fi
PY="$(resolve_python_or_bootstrap 2>/dev/null || command -v python3)"
echo "[run_daily_local] python=$PY"

"$PY" -m infrastructure.scheduling.drift_audit --phase start >/dev/null 2>&1 || \
  echo "[run_daily_local] WARN: drift_audit start 실패 (계속 진행)" >&2

# 0b. PID 락 — 전일 실행이 24h 넘게 미종료된 경우 새 run skip
if [ -f "$LOCK_FILE" ]; then
  prev_pid="$(cat "$LOCK_FILE" 2>/dev/null || echo "")"
  if [ -n "$prev_pid" ] && kill -0 "$prev_pid" 2>/dev/null; then
    echo "[run_daily_local] previous run alive (pid=$prev_pid) — skip" >&2
    exit 0
  fi
  echo "[run_daily_local] stale lock (pid=$prev_pid) — overwrite"
fi
echo $$ > "$LOCK_FILE"
trap 'rm -f "$LOCK_FILE"' EXIT

# 0c. 네트워크 readiness poll (최대 60s)
echo "[run_daily_local] network readiness poll"
NET_READY=0
for i in $(seq 1 60); do
  if curl -sf --max-time 3 -o /dev/null https://opendart.fss.or.kr/ 2>/dev/null; then
    NET_READY=1
    echo "[run_daily_local] network ready after ${i}s"
    break
  fi
  sleep 1
done
if [ "$NET_READY" -ne 1 ]; then
  echo "[run_daily_local] WARN: 60s network wait timeout — graceful 진행 (각 stage skip 가능)" >&2
fi

# 0d. 경로 환경변수 — REPO_ROOT 기준 literal.
DATE_KST="${DATE_OVERRIDE:-$(TZ=Asia/Seoul date +%Y-%m-%d)}"
export TRAIL_TODAY="$REPO_ROOT/operations/$DATE_KST/.trails"
mkdir -p "$TRAIL_TODAY"
echo "[run_daily_local] DATE=$DATE_KST TRAIL_TODAY=$TRAIL_TODAY"

phase_log() {
  local phase="$1"
  echo "$LOG_DIR/${DATE_KST}-${phase}.log"
}

# claude CLI 부재 시 graceful skip — 실제 gating 은 infrastructure/llm dispatcher
# (ClaudeCliAdapter) 가 수행 (F-13). 본 검사는 upfront 안내용 informational only.
if [ -z "$(command -v claude || true)" ]; then
  echo "[run_daily_local] WARN: claude CLI 없음 — LLM stage (4 / 6 / notify) skip 예정" >&2
fi

# 1. Pre-Stage 4 (Stage 0~3 결정적)
echo "[run_daily_local] === 1. pre-stage4 ==="
bash "$REPO_ROOT/applications/daily_pipeline.sh" --date "$DATE_KST" --phase pre-stage4 \
  >> "$(phase_log pre-stage4)" 2>&1 || \
  echo "[run_daily_local] WARN: pre-stage4 non-zero exit (계속)" >&2

# 2. Stage 4 LLM (thesis-auditor) — infrastructure/llm dispatcher 경유 (F-13)
echo "[run_daily_local] === 2. Stage 4 thesis-auditor ==="
"$PY" -m infrastructure.llm.dispatcher \
  --prompt "/investment-stage4-thesis-auditor $DATE_KST" \
  --allowed-tools "Bash,Read,Write,Edit,Glob,Grep" \
  >> "$(phase_log stage4)" 2>&1 || \
  echo "[run_daily_local] WARN: Stage 4 non-zero exit" >&2

# 3. Post-Stage 4 (Stage 5~5d 결정적)
echo "[run_daily_local] === 3. post-stage4 ==="
bash "$REPO_ROOT/applications/daily_pipeline.sh" --date "$DATE_KST" --phase post-stage4 \
  >> "$(phase_log post-stage4)" 2>&1 || \
  echo "[run_daily_local] WARN: post-stage4 non-zero exit" >&2

# 4. Stage 6 LLM (brief-author) — infrastructure/llm dispatcher 경유 (F-13)
echo "[run_daily_local] === 4. Stage 6 brief-author ==="
"$PY" -m infrastructure.llm.dispatcher \
  --prompt "/investment-stage6-brief-author $DATE_KST" \
  --allowed-tools "Bash,Read,Write,Edit,Glob,Grep" \
  >> "$(phase_log stage6)" 2>&1 || \
  echo "[run_daily_local] WARN: Stage 6 non-zero exit" >&2

# 5. Notify manifest 작성
echo "[run_daily_local] === 5. notify dispatcher ==="
BRIEF_PATH="$REPO_ROOT/operations/$DATE_KST/daily-brief.md"
NOTIFY_OUT="$REPO_ROOT/operations/$DATE_KST/_notify-results.json"
if [ -f "$BRIEF_PATH" ]; then
  "$PY" -m infrastructure.notify.dispatcher \
    --brief "$BRIEF_PATH" \
    --out-json "$NOTIFY_OUT" \
    >> "$(phase_log notify)" 2>&1 || \
    echo "[run_daily_local] WARN: notify manifest 작성 실패" >&2
else
  echo "[run_daily_local] WARN: daily-brief.md 부재 — notify skip ($BRIEF_PATH)" >&2
fi

# 6. MCP 알림 발송 — infrastructure/llm dispatcher 가 manifest 읽어 MCP 도구 호출 (F-13)
echo "[run_daily_local] === 6. MCP notify dispatch ==="
if [ -f "$NOTIFY_OUT" ]; then
  PROMPT="다음 파일을 읽고: $NOTIFY_OUT
status=\"sent\" 인 각 채널에 대해 payload 를 그대로 전달한다.
_mcp_tool_hint='slack_send_message' 이면 namespaced 도구 $SLACK_MCP_TOOL,
_mcp_tool_hint='create_draft' 이면 $GMAIL_MCP_TOOL 을 호출.
payload 본문에 새 내용 추가 / 수정 일체 금지. 발송 후 결과 요약만 1줄로 출력."
  "$PY" -m infrastructure.llm.dispatcher \
    --prompt "$PROMPT" \
    --allowed-tools "Read,$SLACK_MCP_TOOL,$GMAIL_MCP_TOOL" \
    >> "$(phase_log notify)" 2>&1 || \
    echo "[run_daily_local] WARN: MCP dispatch non-zero exit" >&2
fi

# 7. audit shadow-portfolio — 결정론 엔진 (F-6: 구 LLM 스킬 회수). state 부재 시 exit 2 (init 안내).
echo "[run_daily_local] === 7. audit shadow-portfolio (deterministic) ==="
"$PY" -m domains.audit_integrity.main --date "$DATE_KST" \
  >> "$(phase_log audit-shadow)" 2>&1 || \
  echo "[run_daily_local] WARN: audit shadow-portfolio non-zero exit (state 미init 시 정상)" >&2

# 8. drift_audit end snapshot
"$PY" -m infrastructure.scheduling.drift_audit --phase end >/dev/null 2>&1 || \
  echo "[run_daily_local] WARN: drift_audit end 실패" >&2

echo "[run_daily_local] $(ts) done — DATE=$DATE_KST"
echo "============================================================"
