#!/usr/bin/env python3
"""Stage 5a — Thesis Sync (thin CLI delegator, F-8 BC layering).

로직은 두 layer 로 분리:
- ``domain/thesis_projection.py``  — 순수 schema-bridge projection (project_edge_source /
                                     project_spec / project_falsifier / collect_citations). IO 0.
- ``application/thesis_sync.py``   — assembly (project_thesis, now_iso_kst 시계) + IO
                                     (candidate 로드 / commit_thesis / envelope).

본 모듈은 ``python -m domains.risk_engine.thesis_sync`` 진입점 + 공개 심볼 re-export.
G6 (projection 결정론, LLM 위임 금지) · G9 (thesis.json write 만) · G20.
"""
from __future__ import annotations

import sys

from domains.risk_engine.application.thesis_sync import (
    OUTPUT_FILENAME,
    SCHEMA_VERSION,
    STAGE4_FILENAME,
    STAGE_NAME,
    load_candidates,
    main,
    project_thesis,
)
from domains.risk_engine.domain.thesis_projection import (
    collect_citations,
    project_edge_source,
    project_falsifier,
    project_spec,
)

__all__ = [
    "SCHEMA_VERSION",
    "STAGE_NAME",
    "STAGE4_FILENAME",
    "OUTPUT_FILENAME",
    "load_candidates",
    "project_edge_source",
    "project_spec",
    "project_falsifier",
    "collect_citations",
    "project_thesis",
    "main",
]


if __name__ == "__main__":
    sys.exit(main())
