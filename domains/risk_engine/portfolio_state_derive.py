#!/usr/bin/env python3
"""Portfolio drawdown / cash% derive (thin CLI delegator, F-8 BC layering).

로직은 두 layer 로 분리:
- ``domain/portfolio_state.py``      — 순수 (DerivedState value object /
                                       compute_drawdown_pct / compute_cash_pct). IO 0.
- ``application/portfolio_state.py`` — orchestration + IO (_account/summary scan / citation /
                                       _account/derived-{date}.json write).

본 모듈은 ``python -m domains.risk_engine.portfolio_state_derive`` 진입점 + 공개 심볼
re-export. G6 (결정론) · G9 (read-only) · G20 (덮어쓰기 금지).
"""
from __future__ import annotations

import sys

from domains.risk_engine.application.portfolio_state import (
    STAGE_NAME,
    _enumerate_summary_dates,
    _load_summary,
    _summary_file,
    derive_state,
    load_derived,
    main,
)
from domains.risk_engine.domain.portfolio_state import (
    DEFAULT_LOOKBACK_DAYS,
    SCHEMA_VERSION,
    DerivedState,
    compute_cash_pct,
    compute_drawdown_pct,
)

from domains.risk_engine import _boundary
from domains.risk_engine.application import portfolio_state as _app_module

# composition root: _boundary 를 application layer 에 주입 (invariant-D — ADR-0005)
_app_module.configure(_boundary)


__all__ = [
    "SCHEMA_VERSION",
    "STAGE_NAME",
    "DEFAULT_LOOKBACK_DAYS",
    "DerivedState",
    "compute_drawdown_pct",
    "compute_cash_pct",
    "derive_state",
    "load_derived",
    "_summary_file",
    "_load_summary",
    "_enumerate_summary_dates",
    "main",
]


if __name__ == "__main__":
    sys.exit(main())
