"""
.claude/hooks/_inject_session_state.py — SessionStart context injection.

Called by inject_session_state.sh (SessionStart, phase 3).
경로는 REPO_ROOT 기준 literal 로 직접 계산 (topology 미경유). 본 script 는
오늘 KST 기준 주요 경로 + 산출물 현황을 plain text 로 stdout 에 출력 → Claude
Code 가 system-reminder 로 표시 → Claude 가 오늘 trail 디렉토리를 바로 알 수 있다.

출력 항목 (4개):
  1. 주요 경로 (오늘 KST trail / audit / positions / user_context)
  2. 오늘 trail 디렉토리 파일 목록 (어떤 stage 산출물이 존재하는지)
  3. 보유 포지션 현황 (telemetry/positions/*.yaml, 없으면 한 줄)
  4. 포트폴리오 컨텍스트 (portfolio.local.yaml → portfolio.yaml 순으로 fallback)

exit code: 항상 0 (warn-only) — 실패해도 세션 차단 안 함.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml


# ──────────────────────────────────────────────────────────────
# Repo root 검출
# ──────────────────────────────────────────────────────────────
def _git_root(start: Path) -> Path:
    try:
        out = subprocess.check_output(
            ["git", "-C", str(start), "rev-parse", "--show-toplevel"],
            stderr=subprocess.DEVNULL,
        ).decode().strip()
        return Path(out)
    except Exception:
        return start.parent.parent


ROOT = _git_root(Path(__file__).resolve().parent)


# ──────────────────────────────────────────────────────────────
# KST 날짜 (macOS date -v 사용, 주말 보정)
# ──────────────────────────────────────────────────────────────
def _kst_dates() -> tuple[str, str]:
    """(today_kst, yesterday_kst) 반환. 실패 시 UTC fallback."""
    try:
        dow = int(subprocess.check_output(
            ["bash", "-c", "TZ=Asia/Seoul date +%u"],
            stderr=subprocess.DEVNULL,
        ).decode().strip())
        raw_today = subprocess.check_output(
            ["bash", "-c", "TZ=Asia/Seoul date +%Y-%m-%d"],
            stderr=subprocess.DEVNULL,
        ).decode().strip()
        yest = subprocess.check_output(
            ["bash", "-c", "TZ=Asia/Seoul date -v -1d +%Y-%m-%d"],
            stderr=subprocess.DEVNULL,
        ).decode().strip()
        if dow == 6:   # 토요일 → 금요일
            today = subprocess.check_output(
                ["bash", "-c", "TZ=Asia/Seoul date -v -1d +%Y-%m-%d"],
                stderr=subprocess.DEVNULL,
            ).decode().strip()
        elif dow == 7:  # 일요일 → 금요일
            today = subprocess.check_output(
                ["bash", "-c", "TZ=Asia/Seoul date -v -2d +%Y-%m-%d"],
                stderr=subprocess.DEVNULL,
            ).decode().strip()
        else:
            today = raw_today
        return today, yest
    except Exception:
        from datetime import datetime, timezone, timedelta
        kst = timezone(timedelta(hours=9))
        now = datetime.now(kst)
        return now.strftime("%Y-%m-%d"), (now - timedelta(days=1)).strftime("%Y-%m-%d")


DATE_TODAY, DATE_YEST = _kst_dates()


def _resolve(key: str) -> Path:
    """주요 경로 키 → 절대경로 (REPO_ROOT 기준 literal, topology 미경유)."""
    rel = {
        "trail_today": f"operations/{DATE_TODAY}",
        "operations_audit": "telemetry/audit",
        "positions": "telemetry/positions",
        "user_context_dir": "config/user",
    }.get(key, key)
    return ROOT / rel


# ──────────────────────────────────────────────────────────────
# 출력 조립
# ──────────────────────────────────────────────────────────────
out: list[str] = [f"[session-state] KST today={DATE_TODAY}"]

# ─── 1. 주요 경로 (오늘 KST) ─────────────────────────────────
out.append("\n## 주요 경로 (오늘 KST)")
for label, key in (
    ("today trail",  "trail_today"),
    ("audit",        "operations_audit"),
    ("positions",    "positions"),
    ("user_context", "user_context_dir"),
):
    out.append(f"  {label:<13} = {_resolve(key)}")

# ─── 2. $TRAIL_TODAY 파일 목록 ───────────────────────────────
trail_today = _resolve("trail_today")
out.append(f"\n## 오늘 trail 파일 목록  ({trail_today})")
if trail_today.exists():
    files = sorted(trail_today.iterdir())
    if files:
        for f in files:
            out.append(f"  {f.name}  ({f.stat().st_size:,}B)")
    else:
        out.append("  (비어 있음 — 오늘 pipeline 미실행)")
else:
    out.append("  (디렉토리 없음 — 오늘 pipeline 미실행)")

# ─── 3. 보유 포지션 현황 ─────────────────────────────────────
positions_dir = _resolve("positions")
out.append(f"\n## 보유 포지션  ({positions_dir})")
if positions_dir.exists():
    pos_files = sorted(positions_dir.glob("*.yaml"))
    if pos_files:
        for pf in pos_files:
            try:
                data = yaml.safe_load(pf.read_text(encoding="utf-8")) or {}
                ticker  = data.get("ticker", pf.stem)
                name    = data.get("name", "")
                status  = data.get("status", "")
                prox    = data.get("falsifier_proximity", {})
                band    = prox.get("band", "") if isinstance(prox, dict) else ""
                out.append(f"  {ticker} {name}  status={status}  falsifier_proximity={band}")
            except Exception:
                out.append(f"  {pf.name}  (parse error)")
    else:
        out.append("  (보유 포지션 없음)")
else:
    out.append("  (positions 디렉토리 없음)")

# ─── 4. 포트폴리오 컨텍스트 ─────────────────────────────────
user_ctx_dir = _resolve("user_context_dir")
portfolio_local   = user_ctx_dir / "portfolio.local.yaml"
portfolio_default = user_ctx_dir / "portfolio.yaml"
target = (
    portfolio_local   if portfolio_local.exists()   else
    portfolio_default if portfolio_default.exists() else
    None
)

out.append("\n## 포트폴리오 컨텍스트")
if target:
    try:
        pf = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
        out.append(f"  total_capital_krw:    {pf.get('total_capital_krw')}")
        out.append(f"  current_drawdown_pct: {pf.get('current_drawdown_pct')}")
        out.append(f"  current_cash_pct:     {pf.get('current_cash_pct')}")
        out.append(f"  volatility_tolerance: {pf.get('volatility_tolerance')}")
        out.append(f"  (source: {target.name})")
    except Exception as e:
        out.append(f"  읽기 실패: {e}")
else:
    out.append("  portfolio.yaml / portfolio.local.yaml 없음 → Stage 5 sizing 출력 보류")

print("\n".join(out), flush=True)
