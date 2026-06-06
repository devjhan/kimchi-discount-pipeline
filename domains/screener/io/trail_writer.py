"""Trail writer — D-Q-2 envelope 으로 ``$TRAIL_TODAY/02-*.json`` 산출.

다른 모듈은 직접 ``json.dump`` 금지. 모든 산출은 본 writer 를 통과해
schema name 보존 + envelope 5필드 + ``.{N}.json`` suffix 가 자동 적용.
"""
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from domains.screener import _boundary
from domains.screener.domain.verdict import ScreenVerdict
from domains.screener.schemas import SCHEMA_FIN_FETCH, SCHEMA_QUALITY_FILTER
from domains._shared.time.clock import AsOfClock


def write_quality_filter(
    clock: AsOfClock,
    verdicts: tuple[ScreenVerdict, ...],
    *,
    config_path: Path | None,
    config_version: str | int | None,
    warnings: list[str] | None = None,
    filename: str = "02-quality-filter.json",
) -> Path:
    """02-quality-filter.json 산출. Stage 3/4/6 / quality-lens 가 read.

    verdict 객체는 ``asdict`` 로 직렬화 — RuleResult 트리도 함께 평탄화.
    dry-run 등 별도 채널로 산출할 때는 ``filename`` 인자로 path 분리.
    """
    date_iso = clock.trading_date.isoformat()
    out_path = (
        _boundary.resolve_path("trail_today", date=date_iso) / filename
    )
    return _boundary.write_envelope(
        out_path,
        {"verdicts": [asdict(v) for v in verdicts]},
        schema=SCHEMA_QUALITY_FILTER,
        date=date_iso,
        config_path=config_path,
        config_version=config_version,
        warnings=warnings,
    )


def write_fin_fetch_summary(
    clock: AsOfClock,
    stats: dict[str, Any],
    *,
    config_path: Path | None,
    config_version: str | int | None,
    warnings: list[str] | None = None,
) -> Path:
    """02-fin-fetch.json audit 추적 산출 (선택)."""
    date_iso = clock.trading_date.isoformat()
    out_path = (
        _boundary.resolve_path("trail_today", date=date_iso) / "02-fin-fetch.json"
    )
    return _boundary.write_envelope(
        out_path,
        {"stats": stats},
        schema=SCHEMA_FIN_FETCH,
        date=date_iso,
        config_path=config_path,
        config_version=config_version,
        warnings=warnings,
    )
