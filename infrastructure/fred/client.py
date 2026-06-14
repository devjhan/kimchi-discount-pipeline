"""
infrastructure/fred/client.py — FRED (Federal Reserve Economic Data) minimal client.

Stage 0 macro regime classifier 의 지표 fetch (yield curve / credit spread /
VIX / breadth) 의존성. macro_regime.py 의 inline 호출 코드를 분리.

Hard guards:
    - G7: 모든 가져온 값에 source citation (FRED@{observation_date}={value})
    - G8: API key 없거나 fetch 실패 시 FetchError raise — caller graceful skip
    - G21: FRED_API_KEY caller 가 read 후 인자로 전달, module 내부 저장 금지
"""

from __future__ import annotations

from datetime import datetime, timedelta

from infrastructure._common.utils import FetchError, safe_http_json

FRED_BASE = "https://api.stlouisfed.org/fred/series/observations"


def has_fred_key(env: dict[str, str]) -> bool:
    """편의 함수 — caller 가 graceful skip 분기 결정 시."""
    return bool(env.get("FRED_API_KEY", "").strip())


def fred_latest(
    api_key: str, series_id: str, observation_end: str
) -> tuple[float, str]:
    """
    FRED series 의 가장 최근 비-결측 observation 1건 반환.

    Args:
        api_key: .env.FRED_API_KEY (caller 책임).
        series_id: FRED series 코드 (예: 'DGS10', 'BAMLH0A0HYM2', 'VIXCLS').
        observation_end: 'YYYY-MM-DD'.

    Returns:
        (value, observation_date).

    Raises:
        FetchError: API 실패 또는 모든 observation 결측.
    """
    if not api_key:
        raise FetchError("FRED_API_KEY missing")
    params = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
        "observation_end": observation_end,
        "sort_order": "desc",
        "limit": 5,
    }
    data = safe_http_json(FRED_BASE, params=params)
    obs = data.get("observations") or []
    for o in obs:
        v = o.get("value")
        if v is None or v == "" or v == ".":
            continue
        try:
            return float(v), str(o.get("date"))
        except (TypeError, ValueError):
            continue
    raise FetchError(
        f"FRED {series_id} returned no usable observation by {observation_end}"
    )


def fred_series(
    api_key: str,
    series_id: str,
    observation_start: str,
    observation_end: str,
) -> list[tuple[str, float]]:
    """
    FRED series 를 [start, end] 구간 으로 fetch. 결측은 skip.

    Returns:
        list of (date, value).

    Raises:
        FetchError: API 실패.
    """
    if not api_key:
        raise FetchError("FRED_API_KEY missing")
    params = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
        "observation_start": observation_start,
        "observation_end": observation_end,
    }
    data = safe_http_json(FRED_BASE, params=params)
    out: list[tuple[str, float]] = []
    for o in data.get("observations") or []:
        v = o.get("value")
        if v in (None, "", "."):
            continue
        try:
            out.append((str(o.get("date")), float(v)))
        except (TypeError, ValueError):
            continue
    return out


def fred_history_values(
    api_key: str,
    series_id: str,
    observation_end: str,
    *,
    years: int = 5,
) -> list[float]:
    """
    최근 `years` 년치 series value list (percentile 계산용 편의 함수).
    """
    end = datetime.strptime(observation_end, "%Y-%m-%d")
    start = end - timedelta(days=365 * years)
    rows = fred_series(
        api_key,
        series_id,
        start.strftime("%Y-%m-%d"),
        observation_end,
    )
    return [v for _, v in rows]


__all__ = [
    "FRED_BASE",
    "has_fred_key",
    "fred_latest",
    "fred_series",
    "fred_history_values",
]
