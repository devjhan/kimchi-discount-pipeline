#!/usr/bin/env bash
# ============================================================
# infrastructure/scheduling/uninstall.sh — install.sh 의 짝 (reversibility)
# ============================================================
#
# 1. launchctl bootout (모든 com.investment_v3.* agent 제거; v2 잔재도 정리)
# 2. ~/Library/LaunchAgents/com.investment_v[23].*.plist 삭제
# 3. sudo pmset repeat cancel (wake schedule 해제)
# 4. governance/schedules.lock.yaml 은 그대로 유지 — governance history 보존
#    (재install 시 동일 SHA 재생산 검증 가능)
#
# 본 스크립트는 governance/schedules.yaml 자체를 건드리지 않는다 — 다음
# install 시 동일 정의로 재배포 가능. 완전 제거를 원하면 schedules.yaml 의
# enabled: false 또는 entry 자체 삭제 후 generator 재실행.
#
# 호출:
#   bash infrastructure/scheduling/uninstall.sh
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

OS="$(uname -s)"
if [ "$OS" != "Darwin" ]; then
  echo "[uninstall] non-Darwin: $OS — 현재 macOS launchd 만 지원" >&2
  exit 1
fi

UID_NUM="$(id -u)"

# 1. launchctl bootout (idempotent)
echo "[uninstall] step 1/3: launchctl bootout"
removed=0
# 마이그레이션 tolerant glob — 신 v3 + 구 v2 잔재 동시 정리 (X-1, _labels.py 동기).
for plist in "$HOME/Library/LaunchAgents/com.investment_v"[23]"."*.plist; do
  [ -f "$plist" ] || continue
  label="$(basename "$plist" .plist)"
  echo "[uninstall]   $label"
  launchctl bootout "gui/$UID_NUM/$label" 2>/dev/null || true
  rm -f "$plist"
  removed=$((removed + 1))
done
echo "[uninstall]   $removed plist 제거됨"

# 2. pmset repeat cancel — wake schedule 해제 (sudo)
echo "[uninstall] step 2/3: pmset repeat cancel (sudo)"
sudo pmset repeat cancel || true
pmset -g sched | head -5

# 3. 사후 검증
echo "[uninstall] step 3/3: 사후 검증"
remaining="$(ls "$HOME/Library/LaunchAgents/com.investment_v"[23]"."*.plist 2>/dev/null | wc -l | tr -d ' ')"
if [ "$remaining" -ne 0 ]; then
  echo "[uninstall] WARN: $remaining plist 잔존" >&2
fi
launchctl print "gui/$UID_NUM/com.investment_v3.daily_pipeline" 2>&1 | head -3 || true

echo "[uninstall] done. governance/schedules.lock.yaml 은 그대로 유지 (history 보존)."
