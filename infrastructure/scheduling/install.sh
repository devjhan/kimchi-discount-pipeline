#!/usr/bin/env bash
# ============================================================
# infrastructure/scheduling/install.sh — OS scheduler 설치 단일 통로
# ============================================================
#
# governance/schedules.yaml (SSoT) 의 모든 enabled schedule 에 대해:
#   1. OS 감지 (현재 macOS launchd 만 지원, Linux systemd / Windows 는 v2)
#   2. .venv 부재 시 bootstrap (PyYAML 의존성 보장)
#   3. launchd_generator.py 호출 → ~/Library/LaunchAgents/*.plist emit
#                                  + schedules.lock.yaml 갱신
#   4. pmset repeat wakeorpoweron 등록 (sudo 1회 요구)
#   5. launchctl bootout (idempotent) + bootstrap → agent 활성
#   6. 사후 검증 (pmset -g sched / launchctl print)
#
# 본 스크립트가 OS 경계의 유일한 진입점. 사용자가 launchctl / pmset 을 직접
# 다루지 않게 한다. 짝 스크립트: uninstall.sh (reversibility 보장).
#
# 호출:
#   bash infrastructure/scheduling/install.sh
#   bash infrastructure/scheduling/install.sh --skip-pmset    # pmset wake 미등록 (디버그용)
#   bash infrastructure/scheduling/install.sh --dry-run       # generator dry-run 까지만
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$REPO_ROOT"

# OS 감지
OS="$(uname -s)"
case "$OS" in
  Darwin) ;;
  Linux)
    echo "[install] Linux systemd generator 미구현 (governance/deployment-residency.md v2 후보)" >&2
    exit 1
    ;;
  *)
    echo "[install] unsupported OS: $OS" >&2
    exit 1
    ;;
esac

# CLI 플래그
DRY_RUN=0
SKIP_PMSET=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)    DRY_RUN=1; shift ;;
    --skip-pmset) SKIP_PMSET=1; shift ;;
    *) echo "[install] unknown arg: $1" >&2; exit 2 ;;
  esac
done

# Python 해석 — .venv 우선, 부재 시 자동 bootstrap.
# shellcheck source=/dev/null
REPO_ROOT="$REPO_ROOT" source "$REPO_ROOT/infrastructure/_common/python_env.sh"
PY="$(REPO_ROOT="$REPO_ROOT" resolve_python_or_bootstrap)"
if [ -z "$PY" ] || [ ! -x "$PY" ]; then
  echo "[install] FATAL: python3 해석 실패" >&2
  exit 2
fi
echo "[install] python=$PY ($("$PY" --version 2>&1))"

# generator / pmset 입력 경로 — REPO_ROOT 기준 literal export. generator 도
# 동일 default 를 setdefault 하므로 standalone 호출도 OK.
export REPO_ROOT
export LAUNCHD_LOG_DIR="$REPO_ROOT/telemetry/logs/launchd"
export SCHEDULER_STATE_DIR="$REPO_ROOT/telemetry/audit/scheduler-state"
export AUDIT_DIR="$REPO_ROOT/telemetry/audit"
export SCHEDULES_PATH="$REPO_ROOT/governance/schedules.yaml"
export SCHEDULES_LOCK_PATH="$REPO_ROOT/governance/schedules.lock.yaml"
export VENV_PYTHON="$PY"

# 로그 디렉토리 보장
mkdir -p "$LAUNCHD_LOG_DIR" "$SCHEDULER_STATE_DIR"

# 1. plist emit
if [ "$DRY_RUN" -eq 1 ]; then
  echo "[install] --dry-run mode — generator 만 dry-run 호출"
  "$PY" -m infrastructure.scheduling.launchd_generator --dry-run
  exit 0
fi

echo "[install] step 1/4: launchd_generator emit"
"$PY" -m infrastructure.scheduling.launchd_generator

# 2. pmset wake schedule (sudo 1회) — generator 와 동형으로 schedules.yaml 의
#    enabled + wake.enabled schedule 만 대상. pmset repeat 는 단일 전역 반복이라:
#      0개 → cancel (disabled 인데 wake 가 남는 고아 방지, S-1)
#      1개 → 등록
#      2+개 → 가장 이른 wake 만 등록 (나머지는 plist WakeSystem 백업) + 경고
echo "[install] step 2/4: pmset repeat wake 등록"
if [ "$SKIP_PMSET" -eq 1 ]; then
  echo "[install] --skip-pmset — pmset 등록 생략"
else
  WAKE_SPEC="$("$PY" - <<'PYEOF'
import os
import sys
from datetime import datetime, timedelta

import yaml

with open(os.environ["SCHEDULES_PATH"], encoding="utf-8") as f:
    d = yaml.safe_load(f) or {}
cands = []
for key, sched in (d.get("schedules") or {}).items():
    if not sched.get("enabled", True):
        continue
    wake = sched.get("wake") or {}
    if not wake.get("enabled", False):
        continue
    cron = sched["cron"].split()
    hh, mm = int(cron[1]), int(cron[0])
    offset = int(wake.get("pre_offset_minutes", 0))
    t = datetime(2000, 1, 1, hh, mm) - timedelta(minutes=offset)
    cands.append((
        t.hour * 60 + t.minute,
        key,
        str(wake.get("mode", "wakeorpoweron")),
        str(wake.get("days_of_week", "MTWRFSU")),
        f"{t.hour:02d}:{t.minute:02d}:00",
    ))
if not cands:
    print("CANCEL")
else:
    cands.sort()
    _, key, mode, days, tstr = cands[0]
    if len(cands) > 1:
        skipped = ", ".join(c[1] for c in cands[1:])
        print(
            f"[install]   WARN: {len(cands)} wake schedules — pmset repeat 단일, "
            f"'{key}' 만 등록 (skip: {skipped})",
            file=sys.stderr,
        )
    print(f"{mode}\t{days}\t{tstr}")
PYEOF
)"
  if [ "$WAKE_SPEC" = "CANCEL" ]; then
    echo "[install]   enabled wake schedule 없음 — pmset repeat cancel (고아 wake 방지)"
    sudo pmset repeat cancel
  else
    IFS=$'\t' read -r WAKE_MODE WAKE_DAYS WAKE_TIME <<<"$WAKE_SPEC"
    echo "[install]   pmset repeat $WAKE_MODE $WAKE_DAYS $WAKE_TIME"
    sudo pmset repeat "$WAKE_MODE" "$WAKE_DAYS" "$WAKE_TIME"
  fi
fi

# 3. launchctl bootstrap (idempotent — bootout 후 재bootstrap)
echo "[install] step 3/4: launchctl bootstrap"
UID_NUM="$(id -u)"
# glob 은 _labels.py LABEL_PREFIX(com.investment_v3) 와 수동 동기 (X-1).
for plist in "$HOME/Library/LaunchAgents/com.investment_v3."*.plist; do
  [ -f "$plist" ] || continue
  label="$(basename "$plist" .plist)"
  echo "[install]   $label"
  launchctl bootout "gui/$UID_NUM/$label" 2>/dev/null || true
  launchctl bootstrap "gui/$UID_NUM" "$plist"
done

# 4. 사후 검증
echo "[install] step 4/4: 사후 검증"
echo "--- pmset -g sched ---"
pmset -g sched | head -10
echo "--- launchctl print (com.investment_v3.daily_pipeline) ---"
launchctl print "gui/$UID_NUM/com.investment_v3.daily_pipeline" 2>&1 | head -20

# 5. drift_audit snapshot — 설치 직후 baseline
"$PY" -m infrastructure.scheduling.drift_audit --phase start >/dev/null 2>&1 || true

echo "[install] done. 매일 wake → launchd fire 가 등록됨. uninstall 은 infrastructure/scheduling/uninstall.sh."
