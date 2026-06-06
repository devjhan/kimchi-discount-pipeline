"""지주사 NAV 시계열 store — cross-BC 공유 kernel (구 ``catalyst/io/nav_history_cache``).

``telemetry/nav-history/{safe_ticker}.jsonl`` (append-only). 경로는
``infrastructure._common.utils.nav_history_dir()`` 경유 (``$NAV_HISTORY_DIR`` env
override 우선 — 테스트 격리 seam). F-14 로 cache/ → telemetry/ 이전.

**writer** = universe ``nav_discount`` enricher (지주사 NAV/discount 계산 후 일별 append).
**reader** = catalyst ``nav_discount_narrowing`` detector (load + detect_narrowing).
두 BC 가 공유하므로 catalyst-local 이 아니라 _shared kernel 에 거주 (positions_store /
profile_registry 동형 — 다중 BC contract).

**재생성 불가** — NAV = Σ(자회사 시총 × 지분율)는 시스템이 합성하는 자기 증거이며
upstream 에 "N일 전 할인율" 재조회 경로가 없다 (price series 의 재fetch 와 비대칭).
따라서 cache/ (통째 ignore) 가 아니라 telemetry/ (git-tracked cross-day 증거).

한 줄 schema: {date, parent, parent_mcap_krw, nav_sum_krw, premium_pct, citations}.
``premium_pct`` 음수 = NAV 할인. nav_discount_narrowing detector 가 load + detect_narrowing 소비.

Hard guards: G6 (NAV 산출은 호출자 책임, 본 module 은 storage 만) / G7 (citations 호출자가
G7 형식) / G20 (append-only).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from infrastructure._common import utils as _utils


def _safe_ticker(ticker: str) -> str:
    return ticker.replace(":", "_").replace("/", "_")


def _cache_path(parent_ticker: str) -> Path:
    base = _utils.nav_history_dir()
    base.mkdir(parents=True, exist_ok=True)
    return base / f"{_safe_ticker(parent_ticker)}.jsonl"


def append_nav_snapshot(
    parent_ticker: str,
    date: str,
    *,
    parent_mcap_krw: float,
    nav_sum_krw: float,
    premium_pct: float,
    citations: list[str] | None = None,
) -> Path:
    """NAV snapshot 1건 append. 호출자가 ``load_nav_history`` 로 중복 사전 체크 권장."""
    p = _cache_path(parent_ticker)
    record: dict[str, Any] = {
        "date": date,
        "parent": parent_ticker,
        "parent_mcap_krw": parent_mcap_krw,
        "nav_sum_krw": nav_sum_krw,
        "premium_pct": premium_pct,
        "citations": list(citations or []),
    }
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return p


def load_nav_history(
    parent_ticker: str, lookback_days: int | None = None
) -> list[dict[str, Any]]:
    """parent_ticker 의 NAV 시계열 load (date 오름차순). 미존재 시 []."""
    p = _cache_path(parent_ticker)
    if not p.exists():
        return []
    out: list[dict[str, Any]] = []
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    out.sort(key=lambda r: str(r.get("date", "")))
    if lookback_days is not None and out:
        from datetime import datetime, timedelta

        latest = max((r.get("date", "") for r in out), default="")
        if latest:
            cutoff_dt = datetime.strptime(latest, "%Y-%m-%d") - timedelta(days=lookback_days)
            cutoff = cutoff_dt.strftime("%Y-%m-%d")
            out = [r for r in out if str(r.get("date", "")) >= cutoff]
    return out


def list_parents() -> list[str]:
    """nav-history store 에 시계열이 쌓인 parent ticker 목록 (정렬, 중복 제거).

    detector 가 config 명시 목록 부재 시 본 함수로 "history 보유 parent" 를 자동
    발견한다 (writer = universe nav_discount enricher 가 일별 적재). 파일명 역변환
    (lossy) 대신 각 jsonl 첫 valid record 의 ``parent`` 필드를 읽어 robust.
    """
    base = _utils.nav_history_dir()
    if not base.exists():
        return []
    parents: set[str] = set()
    for p in sorted(base.glob("*.jsonl")):
        try:
            with p.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    rec = json.loads(line)
                    parent = rec.get("parent")
                    if parent:
                        parents.add(str(parent))
                    break  # 첫 valid record 면 충분
        except (OSError, json.JSONDecodeError):
            continue
    return sorted(parents)


def detect_narrowing(
    history: list[dict[str, Any]], delta_threshold: float
) -> dict[str, Any] | None:
    """NAV 할인 좁힘 검출 (최신 vs 시작 premium_pct). delta = l - e (좁히면 양수).

    delta_threshold 음수 (예: -0.05 = 5%p). |delta_threshold| 이상 좁혀지면 trigger dict, 아니면 None.
    """
    if len(history) < 2:
        return None
    earliest = history[0]
    latest = history[-1]
    e_prem = earliest.get("premium_pct")
    l_prem = latest.get("premium_pct")
    if e_prem is None or l_prem is None:
        return None
    try:
        e_f = float(e_prem)
        l_f = float(l_prem)
    except (TypeError, ValueError):
        return None
    delta = l_f - e_f
    threshold_abs = abs(float(delta_threshold))
    if delta < threshold_abs:
        return None
    return {
        "earliest_date": earliest.get("date"),
        "latest_date": latest.get("date"),
        "earliest_premium_pct": round(e_f, 6),
        "latest_premium_pct": round(l_f, 6),
        "delta": round(delta, 6),
        "delta_threshold_abs": threshold_abs,
        "citations": list(earliest.get("citations") or [])
        + list(latest.get("citations") or []),
    }


__all__ = [
    "append_nav_snapshot",
    "load_nav_history",
    "list_parents",
    "detect_narrowing",
]
