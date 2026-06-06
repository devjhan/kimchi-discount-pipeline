#!/usr/bin/env python3
"""Stage 5d — Thesis Expiry Monitor (thin CLI delegator, F-8 BC layering).

로직은 두 layer 로 분리:
- ``domain/expiry.py``             — 순수 규칙 (ExpiryRecord / 4-tier classify_tier /
                                     DEFAULT_TIERS / DAYS_PER_MONTH). IO 0.
- ``application/thesis_expiry.py`` — orchestration + IO (compute_expiry / positions
                                     로드 / expiry md write / envelope).

본 모듈은 ``python -m domains.risk_engine.thesis_expiry_monitor`` 진입점 + 공개 심볼
re-export. G6 (결정론) · G9 (alert 만) · G20 (덮어쓰기 금지).
"""
from __future__ import annotations

import sys

from domains.risk_engine.application.thesis_expiry import (
    SCHEMA_VERSION,
    STAGE_NAME,
    _write_expiry_md,
    compute_expiry,
    load_open_thesis,
    main,
    render_expiry_md,
)
from domains.risk_engine.domain.expiry import (
    DAYS_PER_MONTH,
    DEFAULT_TIERS,
    ExpiryRecord,
    classify_tier as _classify_tier,
)

from domains.risk_engine import _boundary
from domains.risk_engine.application import thesis_expiry as _app_module

# composition root: _boundary 를 application layer 에 주입 (invariant-D — ADR-0005)
_app_module.configure(_boundary)


__all__ = [
    "SCHEMA_VERSION",
    "STAGE_NAME",
    "DEFAULT_TIERS",
    "DAYS_PER_MONTH",
    "ExpiryRecord",
    "_classify_tier",
    "load_open_thesis",
    "compute_expiry",
    "render_expiry_md",
    "_write_expiry_md",
    "main",
]


if __name__ == "__main__":
    sys.exit(main())
