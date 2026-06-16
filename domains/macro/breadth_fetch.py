"""Stage 0a — SPX breadth auto-fetch.

원래 ``domains/risk_engine/macro_breadth_fetch.py`` 를 본 모듈로 이전. 동작 동일:
``infrastructure/_common/_spx_constituents.json`` cache 의 ticker 마다 Yahoo
public chart 로 200 영업일 close fetch → 200d SMA 계산 → close > SMA200 비율
산출 → ``$EXTERNAL_SIGNALS_MACRO_BREADTH_PATH`` 작성.

Stage 0 (regime classify) 보다 먼저 (Stage 0a) 실행됨 — breadth.yaml 이 Stage 0
의 ``collect_breadth`` 입력.

Hard guards:
- G6: SMA / breadth_pct 계산은 deterministic Python (LLM 위임 금지)
- G7: yaml 본문에 G7 citation (`yahoo_chart@<ts>=<count>`)
- G8: Yahoo HTTP 실패율 ≥ 20% 시 spx_above_200dma_pct=null + skip_reason
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

from domains.macro import _boundary

STAGE_NAME = "stage0a-macro-breadth-fetch"
SCHEMA_VERSION = "investment-external-signal-breadth-v1"

CONSTITUENTS_PATH = "infrastructure/_common/_spx_constituents.json"
SMA_WINDOW = 200
MIN_CLOSES_REQUIRED = 200
MAX_FAIL_RATIO = 0.20
HTTP_PAUSE_SECONDS = 0.05
PERIOD_DAYS = 365


def _load_constituents() -> list[str]:
    p = _boundary.resolve_path("infra_common") / "_spx_constituents.json"
    if not p.exists():
        raise FileNotFoundError(
            f"{CONSTITUENTS_PATH} 미존재. 먼저 python -m domains.macro.spx_constituents_refresh 실행 필요"
        )
    data = json.loads(p.read_text(encoding="utf-8"))
    tickers = (data.get("payload") or {}).get("tickers") or []
    if not tickers:
        raise ValueError(f"{CONSTITUENTS_PATH} 의 tickers 빈 배열")
    return list(tickers)


def _classify_ticker(yahoo_ticker: str) -> str | None:
    """단일 ticker → 'above' | 'below' | None (skip)."""
    try:
        rows = _boundary.yahoo_fetch_daily_ohlcv(yahoo_ticker, period_days=PERIOD_DAYS)
    except _boundary.YahooUnavailable:
        return None
    closes = [r["close"] for r in rows if isinstance(r.get("close"), (int, float))]
    if len(closes) < MIN_CLOSES_REQUIRED:
        return None
    sma200 = sum(closes[-SMA_WINDOW:]) / SMA_WINDOW
    last_close = closes[-1]
    return "above" if last_close > sma200 else "below"


def compute_breadth(
    *, tickers: list[str], pause_seconds: float = HTTP_PAUSE_SECONDS
) -> dict[str, Any]:
    """전체 ticker scan → breadth_pct 또는 abort. G8 graceful degrade."""
    above = 0
    below = 0
    failed = 0
    started_at = _boundary.now_iso_kst()

    for ticker in tickers:
        result = _classify_ticker(ticker.upper())
        if result == "above":
            above += 1
        elif result == "below":
            below += 1
        else:
            failed += 1
        if pause_seconds > 0:
            time.sleep(pause_seconds)

    total = len(tickers)
    used = above + below
    fail_ratio = failed / total if total > 0 else 1.0

    if fail_ratio >= MAX_FAIL_RATIO:
        return {
            "spx_above_200dma_pct": None,
            "observed_at": started_at,
            "constituents_total": total,
            "constituents_used": used,
            "constituents_failed": failed,
            "skip_reason": f"fail_ratio={fail_ratio:.2%} ≥ {MAX_FAIL_RATIO:.0%} (Yahoo throttle / network 의심)",
            "source": _boundary.format_citation(
                "yahoo_chart_partial", started_at, f"{used}/{total}"
            ),
        }

    pct = above / used if used > 0 else None
    return {
        "spx_above_200dma_pct": pct,
        "observed_at": started_at,
        "constituents_total": total,
        "constituents_used": used,
        "constituents_failed": failed,
        "skip_reason": None,
        "source": _boundary.format_citation(
            "yahoo_chart", started_at, f"above={above},below={below},failed={failed}"
        ),
    }


def write_breadth_yaml(result: dict[str, Any], *, no_overwrite: bool = False) -> Path:
    """breadth.yaml 작성. atomic .tmp swap. yaml 의존 회피 — 단순 문자열 빌드."""
    out_path = _boundary.resolve_path("external_signals_macro_breadth")
    if no_overwrite and out_path.exists():
        return out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)

    pct = result["spx_above_200dma_pct"]
    pct_str = "null" if pct is None else f"{pct:.4f}"

    lines = [
        "version: 1",
        f"schema: {SCHEMA_VERSION}",
        "",
        f"spx_above_200dma_pct: {pct_str}",
        "",
        f'observed_at: "{result["observed_at"]}"',
        "",
        f'source: "{result["source"]}"',
    ]
    if result.get("skip_reason"):
        lines.append("")
        lines.append(f'skip_reason: "{result["skip_reason"]}"')
    body = "\n".join(lines) + "\n"

    tmp = out_path.with_suffix(out_path.suffix + ".tmp")
    tmp.write_text(body, encoding="utf-8")
    tmp.replace(out_path)
    return out_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Stage 0a — SPX Macro Breadth Fetch")
    parser.add_argument("--date", default=None, help="(unused — fetch is at-call-time)")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Yahoo HTTP 호출 없이 cache 상태만 출력",
    )
    parser.add_argument(
        "--no-overwrite",
        action="store_true",
        help="breadth.yaml 이 이미 있으면 fetch 결과로 덮어쓰지 않음",
    )
    parser.add_argument(
        "--trail-dir",
        default=None,
        help="(unused — breadth helper 는 trails 가 아닌 _external_signals 에 직접 write)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="최대 처리 ticker 개수 (0=무제한, debug 용)",
    )
    args = parser.parse_args(argv)

    date = _boundary.normalize_to_trading_day(args.date)

    if args.dry_run:
        out_path = _boundary.resolve_path("external_signals_macro_breadth")
        _boundary.emit_summary(
            STAGE_NAME,
            {
                "date": date,
                "mode": "dry-run",
                "exists": out_path.exists(),
            },
            out_path,
        )
        return 0

    tickers = _load_constituents()
    if args.limit > 0:
        tickers = tickers[: args.limit]
    result = compute_breadth(tickers=tickers)
    out_path = write_breadth_yaml(result, no_overwrite=args.no_overwrite)

    # audit envelope — telemetry/audit/breadth/macro-breadth-{date}.json
    audit_dir = _boundary.resolve_path("operations_audit")
    breadth_dir = audit_dir / "breadth"
    breadth_dir.mkdir(parents=True, exist_ok=True)
    audit_path = breadth_dir / f"macro-breadth-{date}.json"
    envelope = _boundary.base_report_envelope(
        schema=SCHEMA_VERSION,
        date=date,
        config_path=str(out_path),
        config_version=1,
    )
    envelope["payload"] = result
    _boundary.write_output_safely(audit_path, envelope)

    _boundary.emit_summary(
        STAGE_NAME,
        {
            "stage": STAGE_NAME,
            "date": date,
            "spx_above_200dma_pct": result["spx_above_200dma_pct"],
            "used": result["constituents_used"],
            "failed": result["constituents_failed"],
            "skip_reason": result["skip_reason"],
        },
        out_path,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
