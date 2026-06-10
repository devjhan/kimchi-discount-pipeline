"""
infrastructure/_common/bootstrap_context.py — SessionStart context bootstrap.

Claude Code 의 ``inject_session_state`` hook (SessionStart) 의 기능을 Python
함수로 재구현. Zed Agent 는 hook 을 지원하지 않으므로, ``AGENTS.md`` 나
``run_daily_local.sh`` 에서 직접 호출해 context block 을 생성한다.

사용:
    # cron pipeline 에서:
    python -m infrastructure._common.bootstrap_context --date 2026-06-10

    # Python import:
    from infrastructure._common.bootstrap_context import get_bootstrap_context

이전 hook 과 달리 경로는 ``infrastructure._common.utils`` 의 path helper
(`trail_dir`, `audit_dir`, `positions_dir` 등) 로 직접 계산한다 (topology 미경유).
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

from infrastructure._common.utils import (
    REPO_ROOT,
    audit_dir,
    normalize_to_trading_day,
    positions_dir,
    repo_path,
    trail_dir,
)

# ──────────────────────────────────────────────────────────────
# 날짜 결정
# ──────────────────────────────────────────────────────────────


def _resolve_date(date_arg: str | None) -> str:
    """입력 날짜 또는 오늘 KST (+주말 보정) 반환."""
    if date_arg:
        return date_arg
    try:
        import subprocess

        dow = int(
            subprocess.check_output(
                ["bash", "-c", "TZ=Asia/Seoul date +%u"],
                stderr=subprocess.DEVNULL,
            )
            .decode()
            .strip()
        )
        raw = (
            subprocess.check_output(
                ["bash", "-c", "TZ=Asia/Seoul date +%Y-%m-%d"],
                stderr=subprocess.DEVNULL,
            )
            .decode()
            .strip()
        )
        if dow == 6:  # 토요일 → 금요일
            return (
                subprocess.check_output(
                    ["bash", "-c", "TZ=Asia/Seoul date -v -1d +%Y-%m-%d"],
                    stderr=subprocess.DEVNULL,
                )
                .decode()
                .strip()
            )
        if dow == 7:  # 일요일 → 금요일
            return (
                subprocess.check_output(
                    ["bash", "-c", "TZ=Asia/Seoul date -v -2d +%Y-%m-%d"],
                    stderr=subprocess.DEVNULL,
                )
                .decode()
                .strip()
            )
        return raw
    except Exception:
        kst = timezone(timedelta(hours=9))
        now = datetime.now(kst)
        return now.strftime("%Y-%m-%d")


# ──────────────────────────────────────────────────────────────
# 컨텍스트 조립
# ──────────────────────────────────────────────────────────────


def get_bootstrap_context(date_kst: str | None = None) -> str:
    """SessionStart 용 bootstrap context plain text 반환.

    ``date_kst`` — KST 거래일 (YYYY-MM-DD). 미지정 시 오늘 KST.
    """
    date_kst = _resolve_date(date_kst)
    trading_day = normalize_to_trading_day(date_kst)

    trail_path = trail_dir(trading_day)
    audit_path = audit_dir()
    pos_path = positions_dir()
    user_ctx_path = repo_path("config/user")

    lines: list[str] = [f"[session-state] KST today={trading_day}"]

    # ─── 1. 주요 경로 ───────────────────────────────────────────
    lines.append("\n## 주요 경로 (오늘 KST)")
    lines.append(f"  today trail    = {trail_path}")
    lines.append(f"  audit          = {audit_path}")
    lines.append(f"  positions      = {pos_path}")
    lines.append(f"  user_context   = {user_ctx_path}")

    # ─── 2. trail 파일 목록 ─────────────────────────────────────
    lines.append(f"\n## 오늘 trail 파일 목록  ({trail_path})")
    if trail_path.exists():
        files = sorted(trail_path.iterdir())
        if files:
            for f in files:
                lines.append(f"  {f.name}  ({f.stat().st_size:,}B)")
        else:
            lines.append("  (비어 있음 — 오늘 pipeline 미실행)")
    else:
        lines.append("  (디렉토리 없음 — 오늘 pipeline 미실행)")

    # ─── 3. 보유 포지션 ─────────────────────────────────────────
    lines.append(f"\n## 보유 포지션  ({pos_path})")
    if pos_path.exists():
        pos_files = sorted(pos_path.glob("*.yaml"))
        if pos_files:
            for pf in pos_files:
                try:
                    data = yaml.safe_load(pf.read_text(encoding="utf-8")) or {}
                    ticker = data.get("ticker", pf.stem)
                    name_val = data.get("name", "")
                    status = data.get("status", "")
                    prox = data.get("falsifier_proximity", {})
                    band = prox.get("band", "") if isinstance(prox, dict) else ""
                    lines.append(
                        f"  {ticker} {name_val}  status={status}  falsifier_proximity={band}"
                    )
                except Exception:
                    lines.append(f"  {pf.name}  (parse error)")
        else:
            lines.append("  (보유 포지션 없음)")
    else:
        lines.append("  (positions 디렉토리 없음)")

    # ─── 4. 포트폴리오 컨텍스트 ─────────────────────────────────
    portfolio_local = user_ctx_path / "portfolio.local.yaml"
    portfolio_default = user_ctx_path / "portfolio.yaml"
    target = (
        portfolio_local
        if portfolio_local.exists()
        else portfolio_default
        if portfolio_default.exists()
        else None
    )

    lines.append("\n## 포트폴리오 컨텍스트")
    if target:
        try:
            pf = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
            lines.append(f"  total_capital_krw:    {pf.get('total_capital_krw')}")
            lines.append(f"  current_drawdown_pct: {pf.get('current_drawdown_pct')}")
            lines.append(f"  current_cash_pct:     {pf.get('current_cash_pct')}")
            lines.append(f"  volatility_tolerance: {pf.get('volatility_tolerance')}")
            lines.append(f"  (source: {target.name})")
        except Exception as e:
            lines.append(f"  읽기 실패: {e}")
    else:
        lines.append(
            "  portfolio.yaml / portfolio.local.yaml 없음 → Stage 5 sizing 출력 보류"
        )

    return "\n".join(lines) + "\n"


# ──────────────────────────────────────────────────────────────
# CLI 진입점
# ──────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bootstrap context generator")
    parser.add_argument(
        "--date", "-d", default=None, help="KST 거래일 (YYYY-MM-DD). 미지정 시 오늘 KST"
    )
    args = parser.parse_args(argv)
    context = get_bootstrap_context(args.date)
    print(context, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
