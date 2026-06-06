#!/usr/bin/env python3
"""Stage 5b — Falsifier Proximity Monitor (thin CLI delegator, F-8 BC layering).

로직은 두 layer 로 분리:
- ``domain/proximity.py``               — 순수 분류 규칙 (ProximityRecord / band classify /
                                          months_between). IO 0.
- ``application/falsifier_proximity.py`` — measurement orchestration + IO (citation /
                                          category dispatch / positions 로드 / drift md write).

본 모듈은 ``python -m domains.risk_engine.falsifier_proximity`` 진입점 + 공개 심볼
re-export. LLM 위임 금지 (G6), 자동 청산 명령 금지 (G9).
"""
from __future__ import annotations

import sys

from domains.risk_engine.application.falsifier_proximity import (
    SCHEMA_VERSION,
    STAGE_NAME,
    _write_drift_md,
    load_open_positions,
    main,
    measure_proximity,
    render_drift_md,
)
from domains.risk_engine.domain.proximity import (
    DEFAULT_PROXIMITY_BANDS,
    ProximityRecord,
    classify as _classify,
    months_between as _months_between,
)

from domains.risk_engine import _boundary
from domains.risk_engine.application import falsifier_proximity as _app_module

# composition root: _boundary 를 application layer 에 주입 (invariant-D — ADR-0005)
_app_module.configure(_boundary)


__all__ = [
    "SCHEMA_VERSION",
    "STAGE_NAME",
    "DEFAULT_PROXIMITY_BANDS",
    "ProximityRecord",
    "_classify",
    "_months_between",
    "load_open_positions",
    "measure_proximity",
    "render_drift_md",
    "_write_drift_md",
    "main",
]


if __name__ == "__main__":
    sys.exit(main())
