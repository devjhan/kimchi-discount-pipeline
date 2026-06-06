#!/usr/bin/env python3
"""
domains/macro/spx_constituents_refresh.py — SPX 구성종목 cache refresh.

`infrastructure/_common/_spx_constituents.json` cache 를 Wikipedia
"List of S&P 500 companies" 페이지에서 ticker symbol 만 추출해 갱신한다.

월 1회 정도 실행으로 충분 — 구성종목 변경은 분기 rebalance 단위. macro_breadth
helper 가 본 cache 를 read 한다.

Hard guards:
    - G7: cache JSON 에 source citation (wikipedia@<ts>=<count>)
    - G8: HTTP / parse 실패 시 cache 미변경 + warning (graceful degrade)
    - G20: cache overwrite 는 atomic .tmp swap; 직전 cache 는 .{N}.json 보존
    - 의존성 zero (urllib + html.parser stdlib)

Run:
    python -m domains.macro.spx_constituents_refresh [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from domains.macro._boundary import (
    FetchError,
    base_report_envelope,
    emit_summary,
    format_citation,
    now_iso_kst,
    resolve_path,
    write_output_safely,
)

SCHEMA_VERSION = "investment-spx-constituents-v1"
STAGE_NAME = "spx-constituents-refresh"
WIKI_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
USER_AGENT = "investment-pipeline/1.0 (+constituents refresh)"


class _SPXTableParser(HTMLParser):
    """Wikipedia '#constituents' table 의 첫 번째 td (Symbol) 만 추출.

    Wikipedia 구조: id='constituents' table 안의 각 row 첫 번째 cell 이 ticker.
    parser 는 'in_target_table' / 'in_row_first_cell' / 'in_anchor' 상태를 트래킹.
    """

    def __init__(self) -> None:
        super().__init__()
        self.tickers: list[str] = []
        self._in_target_table = False
        self._table_depth = 0
        self._cell_depth = 0
        self._row_cell_count = 0
        self._capturing = False
        self._buffer: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        adict = {k: v for k, v in attrs}
        if tag == "table" and adict.get("id") == "constituents":
            self._in_target_table = True
            self._table_depth = 1
            return
        if not self._in_target_table:
            return
        if tag == "table":
            self._table_depth += 1
        elif tag == "tr":
            self._row_cell_count = 0
        elif tag == "td":
            self._cell_depth += 1
            self._row_cell_count += 1
            if self._row_cell_count == 1 and self._table_depth == 1:
                self._capturing = True
                self._buffer = []

    def handle_endtag(self, tag: str) -> None:
        if not self._in_target_table:
            return
        if tag == "table":
            self._table_depth -= 1
            if self._table_depth == 0:
                self._in_target_table = False
        elif tag == "td":
            if self._capturing:
                ticker = "".join(self._buffer).strip().split()[0] if self._buffer else ""
                # Wikipedia uses BRK.B style; Yahoo expects BRK-B
                ticker = ticker.replace(".", "-")
                if ticker and all(c.isalpha() or c == "-" for c in ticker):
                    self.tickers.append(ticker)
                self._capturing = False
                self._buffer = []
            self._cell_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._capturing:
            self._buffer.append(data)


def fetch_constituents(*, timeout: float = 15.0) -> list[str]:
    """Wikipedia HTML → ticker list. 실패 시 FetchError raise."""
    req = urllib.request.Request(WIKI_URL, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except Exception as exc:  # noqa: BLE001
        raise FetchError(f"wikipedia fetch fail: {exc}") from exc

    parser = _SPXTableParser()
    parser.feed(html)
    if len(parser.tickers) < 400:
        raise FetchError(
            f"wikipedia parse: only {len(parser.tickers)} tickers found "
            f"(expected ~500). page structure changed?"
        )
    # de-dup, preserve order
    seen: set[str] = set()
    unique: list[str] = []
    for t in parser.tickers:
        if t not in seen:
            seen.add(t)
            unique.append(t)
    return unique


def cache_path() -> Path:
    return resolve_path("infra_common") / "_spx_constituents.json"


def load_cached() -> dict[str, Any]:
    p = cache_path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _cache_age_days(cached: dict[str, Any]) -> int | None:
    """cached payload 의 observed_at 기준 경과 일수. 미존재/파싱불가 시 None (= stale)."""
    observed = cached.get("payload", {}).get("observed_at")
    if not observed:
        return None
    try:
        obs = datetime.fromisoformat(str(observed))
        now = datetime.fromisoformat(now_iso_kst())
        return (now - obs).days
    except (ValueError, TypeError):
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SPX constituents cache refresh")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="HTTP fetch 없이 현 cache 상태만 출력",
    )
    parser.add_argument(
        "--max-age-days",
        type=int,
        default=30,
        help="cache 가 N일 이내면 fetch self-skip (기본 30 — 구성종목은 분기 rebalance). "
        "0=항상 fetch. daily_pipeline 선두에서 무조건 호출해도 저비용 (D-2).",
    )
    args = parser.parse_args(argv)

    out_path = cache_path()

    if args.dry_run:
        cached = load_cached()
        msg = {
            "stage": STAGE_NAME,
            "dry_run": True,
            "cache_path": str(out_path),
            "cache_exists": out_path.exists(),
            "cached_count": len(cached.get("payload", {}).get("tickers", [])),
            "cached_observed_at": cached.get("payload", {}).get("observed_at"),
        }
        emit_summary(STAGE_NAME, msg, Path("/dev/null"))
        return 0

    # staleness gate — cache 가 max_age_days 이내면 self-skip (D-2 daily 무조건 호출).
    if args.max_age_days > 0:
        age = _cache_age_days(load_cached())
        if age is not None and age < args.max_age_days:
            emit_summary(
                STAGE_NAME,
                {"stage": STAGE_NAME, "skipped": "fresh", "age_days": age,
                 "max_age_days": args.max_age_days},
                Path("/dev/null"),
            )
            return 0

    ts = now_iso_kst()
    try:
        tickers = fetch_constituents()
    except FetchError as exc:
        print(f"[WARN] {STAGE_NAME}: {exc} — cache unchanged", file=sys.stderr)
        return 0  # graceful degrade

    envelope = base_report_envelope(
        schema=SCHEMA_VERSION,
        date=ts.split("T")[0],
        config_path=str(out_path),
        config_version=1,
    )
    envelope["payload"] = {
        "tickers": tickers,
        "count": len(tickers),
        "observed_at": ts,
        "source": format_citation("wikipedia/List_of_S&P_500_companies", ts, len(tickers)),
    }
    written = write_output_safely(out_path, envelope)
    emit_summary(
        STAGE_NAME,
        {"stage": STAGE_NAME, "count": len(tickers), "file": str(written)},
        written,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
