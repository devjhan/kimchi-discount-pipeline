#!/usr/bin/env bash
set -uo pipefail
# ============================================================
# [DEPRECATED 2026-05-13] applications/cloud_routine_run.sh
# ============================================================
# 본 스크립트는 deprecated 됨. KIS / DART / KRX API 의 cloud provider IP
# 차단으로 cloud routine 경로가 무력화됨 (2026-05-12, 2026-05-13 양일 확인).
#
# 대체 진입점: applications/run_daily_local.sh (로컬 launchd primary)
# 근거 spec:   governance/specs/deployment-residency.md
# 삭제 예정:   없음 — IP 정책 변경 시 재활성 후보로 보존.
#
# 실행 시 즉시 exit 1 — 우회 실행 차단. 재활성 조건은 deployment-residency
# spec §5 참조. 본 deprecation 표시는 banner + first_line_exit 2중.
# ============================================================
echo "[DEPRECATED] cloud_routine_run.sh — 본 경로는 IP 차단으로 무력화됨." >&2
echo "             대체: bash applications/run_daily_local.sh" >&2
echo "             spec: governance/specs/deployment-residency.md" >&2
exit 1

# ↓ 이하 원본 본문 FROZEN — 재활성 전용 reference 일 뿐 실행 경로 아님.
#   리팩토링 / rename sweep 에서 제외할 것 (unreachable code 이므로 stale 참조가
#   남아도 무해; 손대면 churn 만 발생 — cf. 2026-06 stale-audit I-1). 재활성 조건:
#   governance/specs/deployment-residency.md §5 (그때 위 banner 제거 + 본문 갱신).
# ============================================================
# applications/cloud_routine_run.sh (원본)
# ============================================================
#
# Anthropic-managed Claude Code Routines (cloud) 에서 호출하는 orchestrator.
# 본 script 는 "deterministic helper 부분" 만 실행한다 — Stage 4 thesis-auditor /
# Stage 6 brief-author / Slack-Gmail dispatch 는 routine prompt 본문이 LLM skill
# / MCP tool 로 직접 수행 (Bash 가 LLM skill 을 부르는 구조 회피).
#
# 본 script 가 daily_pipeline.sh 와 다른 점:
#   1) Stage 0a (macro_breadth_fetch) 가 daily_pipeline.sh 와 동일하게 포함되지만,
#      cloud network policy 가 Custom 으로 yahoo.com 허용되어야 정상 동작.
#   2) KIS_ACCOUNT_NUMBER 가 cloud env 에 주입되었으면 추가로
#      `domains.risk_engine.positions_sync` 호출 (G9b 정책 활성 + 환경변수 set
#      양쪽 만족 시 실제 sync, 아니면 graceful skip).
#   3) 모든 stage 산출물은 cloud session 의 worktree 에 그대로 떨어진다.
#      daily-brief.md 는 routine prompt 가 별도로 git commit + push (claude/
#      branch).  trail JSON 은 cloud session ephemeral.
#
# Hard guards:
#   - G9 (자동 매매 절대 금지) — 본 script 는 매매/주문 명령 0건. positions_sync
#     는 read-only whitelist 만 호출.
#   - G21 — secret env 는 stdout/log 에 echo 금지 (python helper 가 redact).
#   - 한 stage 실패해도 다음 stage 시도 (graceful degrade).
#
# 호출:
#   bash applications/cloud_routine_run.sh                    # 오늘 (KST)
#   bash applications/cloud_routine_run.sh --date 2026-05-09
#   bash applications/cloud_routine_run.sh --dry-run
# ============================================================

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT" || exit 2

PYTHON_BIN="${PYTHON_BIN:-python3}"

DATE_KST="$(TZ=Asia/Seoul date +%Y-%m-%d)"
DRY_RUN_FLAG=""
TRAIL_DIR_OVERRIDE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)       DRY_RUN_FLAG="--dry-run"; shift ;;
    --date)          DATE_KST="$2"; shift 2 ;;
    --date=*)        DATE_KST="${1#--date=}"; shift ;;
    --trail-dir)     TRAIL_DIR_OVERRIDE="$2"; shift 2 ;;
    --trail-dir=*)   TRAIL_DIR_OVERRIDE="${1#--trail-dir=}"; shift ;;
    *)               echo "[ERROR] unknown arg: $1" >&2; exit 2 ;;
  esac
done

LOG_DIR="$REPO_ROOT/telemetry/logs/cron"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/cloud-run-${DATE_KST}.log"

if [[ -n "$TRAIL_DIR_OVERRIDE" ]]; then
  TRAIL_TODAY="$TRAIL_DIR_OVERRIDE"
else
  TRAIL_TODAY="$REPO_ROOT/operations/$DATE_KST"
fi
mkdir -p "$TRAIL_TODAY"
export TRAIL_TODAY

echo "============================================================" | tee -a "$LOG_FILE"
echo "[$(date -Iseconds)] cloud_routine_run — date=$DATE_KST $DRY_RUN_FLAG" | tee -a "$LOG_FILE"
echo "repo=$REPO_ROOT" | tee -a "$LOG_FILE"
echo "trail=$TRAIL_TODAY" | tee -a "$LOG_FILE"
echo "============================================================" | tee -a "$LOG_FILE"

# ------------------------------------------------------------
# Periodic refresh gate — cache 가 stale 하면 자동 refresh.
#   - SPX constituents 캐시 > 30일 → spx_constituents_refresh
#   - KRX holidays last_year < 현재 연도 → infrastructure.krx.refresh_holidays
# 본 gate 는 cloud routine 의 무한 daily 실행 안에서 cache 갱신을 자동화한다.
# 로컬 daily_pipeline.sh 는 본 gate 미포함 — manual invoke 권장.
# ------------------------------------------------------------
echo "" | tee -a "$LOG_FILE"
echo "--- Periodic refresh gate ---" | tee -a "$LOG_FILE"
export REPO_ROOT
"$PYTHON_BIN" - <<'PYEOF' 2>&1 | tee -a "$LOG_FILE" || true
"""Cache staleness check + opt-in refresh trigger."""
import json
import os
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

KST = timezone(timedelta(hours=9))
today = datetime.now(KST).date()

ROOT = Path(os.environ.get("REPO_ROOT", "."))
spx_cache = ROOT / "infrastructure/_common/_spx_constituents.json"
krx_cache = ROOT / "infrastructure/_common/_holidays_krx.json"

# SPX cache age
if spx_cache.exists():
    age_days = (today - datetime.fromtimestamp(spx_cache.stat().st_mtime, KST).date()).days
    print(f"[refresh-gate] spx_constituents cache age = {age_days}d")
    if age_days > 30:
        print("[refresh-gate] spx_constituents stale → refresh")
        subprocess.run(
            [sys.executable, "-m", "domains.macro.spx_constituents_refresh"],
            check=False, cwd=str(ROOT),
        )
else:
    print("[refresh-gate] spx_constituents cache 미존재 → refresh")
    subprocess.run(
        [sys.executable, "-m", "domains.macro.spx_constituents_refresh"],
        check=False, cwd=str(ROOT),
    )

# KRX holidays cache age
if krx_cache.exists():
    try:
        data = json.loads(krx_cache.read_text(encoding="utf-8"))
        years = sorted(set(int(d[:4]) for d in (data.get("dates") or [])))
        last_year = years[-1] if years else 0
    except Exception:
        last_year = 0
    print(f"[refresh-gate] krx_holidays last_year = {last_year}, today.year = {today.year}")
    if last_year < today.year:
        print("[refresh-gate] krx_holidays stale → refresh")
        subprocess.run(
            [sys.executable, "-m", "infrastructure.krx.refresh_holidays"],
            check=False, cwd=str(ROOT),
        )
else:
    print("[refresh-gate] krx_holidays cache 미존재 → refresh")
    subprocess.run(
        [sys.executable, "-m", "infrastructure.krx.refresh_holidays"],
        check=False, cwd=str(ROOT),
    )

print("[refresh-gate] done")
PYEOF

# delegate to daily_pipeline.sh — phase=pre-stage4 (Stage 0~3 만 실행).
# Stage 5~5d 는 Stage 4 LLM skill 후 routine prompt 가 동일 script 를
# --phase post-stage4 로 재호출 (Fix 4: Stage 4→5 sequencing enforce).
REPO_ROOT="$REPO_ROOT" bash "$REPO_ROOT/applications/daily_pipeline.sh" \
  --date "$DATE_KST" \
  --phase pre-stage4 \
  $DRY_RUN_FLAG \
  ${TRAIL_DIR_OVERRIDE:+--trail-dir "$TRAIL_DIR_OVERRIDE"} \
  2>&1 | tee -a "$LOG_FILE"

echo "" | tee -a "$LOG_FILE"
echo "============================================================" | tee -a "$LOG_FILE"
echo "[$(date -Iseconds)] cloud_routine_run complete — date=$DATE_KST (pre-stage4 phase)" | tee -a "$LOG_FILE"
echo "Next steps (routine prompt 본문에서 실행):" | tee -a "$LOG_FILE"
echo "  1. /investment-stage4-thesis-auditor   $DATE_KST" | tee -a "$LOG_FILE"
echo "  2. bash applications/daily_pipeline.sh --date $DATE_KST --phase post-stage4   # Stage 5~5d (Stage 4 산출 consume)" | tee -a "$LOG_FILE"
echo "  3. /investment-stage6-brief-author     $DATE_KST" | tee -a "$LOG_FILE"
echo "  4. python -m infrastructure.notify.dispatcher --brief operations/$DATE_KST/daily-brief.md --out-json $TRAIL_TODAY/_notify-results.json" | tee -a "$LOG_FILE"
echo "  5. routine prompt 가 dispatcher 결과의 payload 를 받아 Slack/Gmail MCP 도구로 송신" | tee -a "$LOG_FILE"
echo "  6. git checkout -b claude/brief-$DATE_KST; git add operations/$DATE_KST/ telemetry/ config/; git commit; git push origin HEAD" | tee -a "$LOG_FILE"
echo "Outputs in: $TRAIL_TODAY/" | tee -a "$LOG_FILE"
echo "Cloud run log: $LOG_FILE" | tee -a "$LOG_FILE"
echo "============================================================" | tee -a "$LOG_FILE"
