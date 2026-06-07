#!/usr/bin/env bash
# ============================================================
# applications/daily_pipeline.sh — investment_v3 manual orchestrator
# ============================================================
#
# !!! 중요 !!!
# 본 script 는 applications/ 의 manual orchestrator 이며, crontab /
# scheduled-tasks 에 직접 등록되지 않는다 (launchd 는 run_daily_local.sh 를
# 호출하고, 그 안에서 본 script 를 phase 별로 부른다). 직접 자동 cron 등록은
# investment_v3 의 명시적 design decision 으로 금지한다.
#
# 호출 방법:
#   bash applications/daily_pipeline.sh                    # 오늘 (KST), --phase all
#   bash applications/daily_pipeline.sh --date 2026-05-08
#   bash applications/daily_pipeline.sh --date 2026-05-08 --dry-run
#   bash applications/daily_pipeline.sh --phase pre-stage4  # Stage 0~3 (cloud routine 1단계)
#   bash applications/daily_pipeline.sh --phase post-stage4 # Stage 5~5d (Stage 4 LLM skill 후)
#
# Stage 0 → 1 → 2 → 3 → 5 의 deterministic helper 만 실행한다.
# Stage 4 (thesis-auditor) 와 Stage 6 (brief-author) 는 LLM skill 이므로
# Claude Code 안에서 별도로 invoke (`/investment-stage4-thesis-auditor` etc).
#
# --phase 분리 이유:
#   Stage 5 sizing 은 Stage 4 thesis-auditor 산출물 (`04-thesis-candidates.json`)
#   을 입력으로 받는다. 그러나 Stage 4 는 LLM skill 이라 shell 에서 직접
#   호출 불가 → cloud routine 은 (1) pre-stage4 → (2) Stage 4 skill → (3)
#   post-stage4 순으로 두 번 본 script 를 호출한다. 로컬 manual 실행은
#   --phase all (default) 로 호환 — 단 Stage 5 는 Stage 4 없이 실행되므로
#   thesis 검증 반영을 원하면 사용자가 Stage 4 skill 후 --phase post-stage4
#   를 재호출.
#
# Stage helper 산출물 (00-* ~ 05*) 은 `operations/{date}/.trails/` (= $TRAIL_TODAY) 에 저장.
# Stage 6 brief 만 그 부모인 `operations/{date}/daily-brief.md` (= $DAILY_BRIEF_PATH).
# 덮어쓰기 금지 — 같은 날 재실행 시 `.{N}.json` suffix 로 보존 (G20).
#
# Hard guards:
#   - G9:  자동 매매 명령 절대 없음. 본 script 는 read/research 전용.
#   - G21: secret env 는 stdout/log 에 echo 금지 (python helper 가 redact).
#   - 한 stage 실패해도 다음 stage 시도 (graceful degrade).
# ============================================================

set -u

# repo root 검출 (script 위치 기반)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT" || exit 2

# Python 인터프리터 — .venv 우선 (PyYAML 등 deps 격리).
# 단일 SSoT: infrastructure/_common/python_env.sh::resolve_python.
# 사용자 override 는 PYTHON_BIN env 로 가능.
if [ -z "${PYTHON_BIN:-}" ]; then
    PYTHON_ENV="$REPO_ROOT/infrastructure/_common/python_env.sh"
    if [ -f "$PYTHON_ENV" ]; then
        # shellcheck source=/dev/null
        REPO_ROOT="$REPO_ROOT" source "$PYTHON_ENV"
        PYTHON_BIN="$(REPO_ROOT="$REPO_ROOT" resolve_python 2>/dev/null || command -v python3)"
    else
        PYTHON_BIN="$(command -v python3)"
    fi
fi
export PYTHON_BIN

# CLI flags
DATE_KST="$(TZ=Asia/Seoul date +%Y-%m-%d)"
DRY_RUN_FLAG=""
TRAIL_DIR_OVERRIDE=""
PHASE="all"   # all | pre-stage4 | post-stage4

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)
      DRY_RUN_FLAG="--dry-run"
      shift
      ;;
    --date)
      DATE_KST="$2"
      shift 2
      ;;
    --date=*)
      DATE_KST="${1#--date=}"
      shift
      ;;
    --trail-dir)
      TRAIL_DIR_OVERRIDE="$2"
      shift 2
      ;;
    --trail-dir=*)
      TRAIL_DIR_OVERRIDE="${1#--trail-dir=}"
      shift
      ;;
    --phase)
      PHASE="$2"
      shift 2
      ;;
    --phase=*)
      PHASE="${1#--phase=}"
      shift
      ;;
    *)
      echo "[ERROR] unknown arg: $1" >&2
      exit 2
      ;;
  esac
done

case "$PHASE" in
  all|pre-stage4|post-stage4) ;;
  *)
    echo "[ERROR] unknown --phase value: $PHASE (allowed: all | pre-stage4 | post-stage4)" >&2
    exit 2
    ;;
esac

# 로그 디렉토리 — telemetry/logs/cron/
LOG_DIR="$REPO_ROOT/telemetry/logs/cron"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/run-${DATE_KST}.log"

# Trail dir 결정 (override 없으면 default).
# --trail-dir override 는 full path (caller 가 .trails/ 포함 여부 결정).
# brief 는 operations/{date}/daily-brief.md ($DAILY_BRIEF_PATH — 부모 디렉토리 루트).
if [[ -n "$TRAIL_DIR_OVERRIDE" ]]; then
  TRAIL_TODAY="$TRAIL_DIR_OVERRIDE"
else
  TRAIL_TODAY="$REPO_ROOT/operations/$DATE_KST/.trails"
fi
mkdir -p "$TRAIL_TODAY"
export TRAIL_TODAY

echo "============================================================" | tee -a "$LOG_FILE"
echo "[$(date -Iseconds)] investment_v3 pipeline run — date=$DATE_KST $DRY_RUN_FLAG" | tee -a "$LOG_FILE"
echo "repo=$REPO_ROOT" | tee -a "$LOG_FILE"
echo "trail=$TRAIL_TODAY" | tee -a "$LOG_FILE"
echo "============================================================" | tee -a "$LOG_FILE"

# ------------------------------------------------------------
# USER_ACKNOWLEDGED gate — Day-1 활성화 게이트.
#   governance/runtime-policy.yaml (base) + runtime-policy.local.yaml
#   (사용자 override) merge 결과의 user_acknowledged 3 flag 모두 true 가
#   아니면 helper 가 산출은 하되 사이즈 / 권고는 보류.  본 script 자체는
#   graceful run 을 막지 않으며 (G8 정합), Python helper 가 각자 G12
#   boundary 를 enforce. 본 게이트는 사용자에게 가시화만.
# ------------------------------------------------------------
ACK_STATUS="$("$PYTHON_BIN" - <<'PYEOF' 2>/dev/null
from infrastructure._common.utils import all_user_acknowledged
ok, pending = all_user_acknowledged()
print("OK" if ok else "PENDING:" + ",".join(pending))
PYEOF
)"
if [[ "$ACK_STATUS" == OK ]]; then
  echo "[gate] user_acknowledged: all true (system armed)" | tee -a "$LOG_FILE"
elif [[ "$ACK_STATUS" == PENDING:* ]]; then
  PENDING="${ACK_STATUS#PENDING:}"
  echo "[gate] user_acknowledged pending: $PENDING" | tee -a "$LOG_FILE"
  echo "       Stage 5 사이즈 권고는 출력 보류 / 다른 stage 는 정상 실행" | tee -a "$LOG_FILE"
  echo "       see governance/procedures/config-files-reference.md" | tee -a "$LOG_FILE"
else
  echo "[gate] user_acknowledged check 실패 (runtime-policy yaml read 불가) — graceful degrade" | tee -a "$LOG_FILE"
fi
echo "============================================================" | tee -a "$LOG_FILE"

run_stage() {
  local stage_name="$1"
  local module_path="$2"
  echo "" | tee -a "$LOG_FILE"
  echo "--- $stage_name ---" | tee -a "$LOG_FILE"
  local extra_flag=""
  if [[ -n "$TRAIL_DIR_OVERRIDE" ]]; then
    extra_flag="--trail-dir $TRAIL_DIR_OVERRIDE"
  fi
  # shellcheck disable=SC2086
  if "$PYTHON_BIN" -m "$module_path" --date "$DATE_KST" $DRY_RUN_FLAG $extra_flag 2>&1 | tee -a "$LOG_FILE"; then
    echo "[OK]   $stage_name" | tee -a "$LOG_FILE"
    return 0
  else
    local rc=${PIPESTATUS[0]}
    echo "[FAIL] $stage_name — exit=$rc (다음 stage 는 시도)" | tee -a "$LOG_FILE"
    return "$rc"
  fi
}

# Periodic raw-data cache refresh (D-2) — daily 선두에서 자동 갱신.
#   스크립트 내부 staleness gate (spx: --max-age-days 30 / krx: annual) 로 fresh 시
#   self-skip 하므로 매일 무조건 호출해도 저비용. run_stage 미사용 — refresh 는
#   --date 무관 (cache 는 날짜 독립) + fetch 실패 graceful degrade (exit 0).
refresh_cache() {
  local name="$1"
  local mod="$2"
  echo "" | tee -a "$LOG_FILE"
  echo "--- $name ---" | tee -a "$LOG_FILE"
  # shellcheck disable=SC2086
  "$PYTHON_BIN" -m "$mod" $DRY_RUN_FLAG 2>&1 | tee -a "$LOG_FILE" \
    || echo "[skip] $name (graceful degrade)" | tee -a "$LOG_FILE"
}

# Deterministic helpers — phase 분리.
#   pre-stage4  : Stage 0~3 (Stage 4 LLM skill 의 input 준비)
#   post-stage4 : Stage 5~5d (Stage 4 LLM skill 산출물 consume)
#   all         : 위 두 phase 순차 — 로컬 manual 실행 호환 (Stage 5 는 Stage 4 없이 실행됨)
echo "[phase] $PHASE" | tee -a "$LOG_FILE"

if [[ "$PHASE" == "all" || "$PHASE" == "pre-stage4" ]]; then
  run_stage "Positions Sync (KIS read-only)"   "domains.risk_engine.positions_sync"
  run_stage "Portfolio State Derive"           "domains.risk_engine.portfolio_state_derive"
  # raw-data 캐시 자동 갱신 (D-2) — breadth_fetch(spx 소비) 앞에서 선행.
  refresh_cache "SPX constituents refresh"     "domains.macro.spx_constituents_refresh"
  refresh_cache "KRX holidays refresh"         "infrastructure.krx.refresh_holidays"
  run_stage "Stage 0a — Macro Breadth Fetch"   "domains.macro.breadth_fetch"
  run_stage "Stage 0  — Macro Regime"          "domains.macro.main"
  run_stage "Stage 1  — Universe Build (sources + enrichers)" "domains.universe.main"
  # NOTE: 2026-05-17 — Stage 1b (NAV calc) + Stage 1c (pref spread) 는 universe.main
  # 의 nav_discount / spread_zscore enricher 로 통합 (Run 5). 별도 stage 호출 불필요.
  run_stage "Stage 2  — Screener (DART fetch + Quality Filter)" "domains.screener.main"
  # 2026-06-04 catalyst BC 승격 (F-7): 구 3 step (3a index-deletion fetch / 3b
  # earnings-panic fetch / 3 catalyst-scan, 중간 JSON IPC) → 1 step. 2 fetch helper
  # 는 detector io 로 흡수되어 중간 산출물 (03-index-deletion / 03-earnings-panic) 제거.
  run_stage "Stage 3  — Catalyst Scan"         "domains.catalyst.main"
fi

# Stage 4 = LLM skill (invest-stage4-thesis-auditor) — 본 script 는 helper 만 자동화.
# cloud routine 의 경우 본 script 를 --phase pre-stage4 로 호출 → Stage 4 LLM
# skill 호출 → 다시 --phase post-stage4 로 재호출. 로컬 manual 은 --phase all
# 로 한 번에 실행되며, 이 경우 Stage 5 는 Stage 4 없이 빈 thesis_candidates 로
# 실행됨 (G11 default no-action 정합).
if [[ "$PHASE" == "all" ]]; then
  echo "[phase] all — Stage 5 가 Stage 4 산출 없이 실행됨 (G11 default no-action 정합). thesis 검증 반영하려면 Stage 4 LLM skill 후 --phase post-stage4 재실행." | tee -a "$LOG_FILE"
fi

if [[ "$PHASE" == "all" || "$PHASE" == "post-stage4" ]]; then
  run_stage "Stage 5  — Sizing Recommendation" "domains.risk_engine.sizing"
  # Stage 5a 는 accepted new_entry 후보 → thesis.json 파생 (5b/5c/5d monitor 입력).
  # 반드시 monitor 보다 먼저 실행 (갓 파생된 thesis.json 을 보도록).
  run_stage "Stage 5a — Thesis Sync (thesis.json)" "domains.risk_engine.thesis_sync"
  run_stage "Stage 5b — Falsifier Proximity"   "domains.risk_engine.falsifier_proximity"
  run_stage "Stage 5c — Event Falsifier Linker" "domains.risk_engine.event_falsifier_linker"
  run_stage "Stage 5d — Thesis Expiry Monitor" "domains.risk_engine.thesis_expiry_monitor"
fi
# Stage 6 = LLM skill (invest-stage6-brief-author).

echo "" | tee -a "$LOG_FILE"
echo "============================================================" | tee -a "$LOG_FILE"
echo "[$(date -Iseconds)] Pipeline run complete — date=$DATE_KST phase=$PHASE" | tee -a "$LOG_FILE"
if [[ "$PHASE" == "pre-stage4" ]]; then
  echo "Manual next step (Claude Code 안에서):" | tee -a "$LOG_FILE"
  echo "  1. /investment-stage4-thesis-auditor   $DATE_KST" | tee -a "$LOG_FILE"
  echo "  2. bash applications/daily_pipeline.sh --date $DATE_KST --phase post-stage4   # Stage 5~5d" | tee -a "$LOG_FILE"
  echo "  3. /investment-stage6-brief-author     $DATE_KST" | tee -a "$LOG_FILE"
elif [[ "$PHASE" == "post-stage4" ]]; then
  echo "Manual next step (Claude Code 안에서):" | tee -a "$LOG_FILE"
  echo "  1. /investment-stage6-brief-author     $DATE_KST" | tee -a "$LOG_FILE"
else
  echo "Manual next step (Claude Code 안에서):" | tee -a "$LOG_FILE"
  echo "  1. /investment-stage4-thesis-auditor   $DATE_KST" | tee -a "$LOG_FILE"
  echo "  2. (선택) bash applications/daily_pipeline.sh --date $DATE_KST --phase post-stage4   # Stage 4 검증 반영한 sizing 재산출" | tee -a "$LOG_FILE"
  echo "  3. /investment-stage6-brief-author     $DATE_KST" | tee -a "$LOG_FILE"
fi
echo "  Optional:" | tee -a "$LOG_FILE"
echo "  - /investment-stage0-regime-labeler    $DATE_KST" | tee -a "$LOG_FILE"
echo "  - /investment-stage2-quality-lens      $DATE_KST" | tee -a "$LOG_FILE"
echo "  - python -m domains.audit_integrity.main --date $DATE_KST   # 4-tier shadow portfolio (결정론, F-6)" | tee -a "$LOG_FILE"
echo "Outputs in: $TRAIL_TODAY/" | tee -a "$LOG_FILE"
echo "Cron log:   $LOG_FILE" | tee -a "$LOG_FILE"
echo "============================================================" | tee -a "$LOG_FILE"
