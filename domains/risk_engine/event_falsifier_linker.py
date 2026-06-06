#!/usr/bin/env python3
"""Stage 5c — Event Falsifier Linker (thin CLI delegator, F-8 BC layering).

로직은 두 layer 로 분리:
- ``domain/event_trigger.py``                — 순수 (EventTriggerStatus value object /
                                               build_stage3_index lookup). IO 0.
- ``application/event_falsifier_linker.py``  — cross-reference 판정 (evaluate_position /
                                               citation) + IO (positions / Stage 3 로드 / write).

본 모듈은 ``python -m domains.risk_engine.event_falsifier_linker`` 진입점 + 공개 심볼
re-export. G6 (순수 lookup, LLM inference 금지) · G9 (alert 만) · G20.
"""
from __future__ import annotations

import sys

from domains.risk_engine.application.event_falsifier_linker import (
    OUTPUT_FILENAME_PREFIX,
    SCHEMA_VERSION,
    STAGE3_FILENAME,
    STAGE_NAME,
    evaluate_position,
    load_event_trigger_positions,
    load_stage3_catalysts,
    main,
)
from domains.risk_engine.domain.event_trigger import (
    EventTriggerStatus,
    build_stage3_index as _build_stage3_index,
)

from domains.risk_engine import _boundary
from domains.risk_engine.application import event_falsifier_linker as _app_module

# composition root: _boundary 를 application layer 에 주입 (invariant-D — ADR-0005)
_app_module.configure(_boundary)


__all__ = [
    "SCHEMA_VERSION",
    "STAGE_NAME",
    "OUTPUT_FILENAME_PREFIX",
    "STAGE3_FILENAME",
    "EventTriggerStatus",
    "_build_stage3_index",
    "load_event_trigger_positions",
    "load_stage3_catalysts",
    "evaluate_position",
    "main",
]


if __name__ == "__main__":
    sys.exit(main())
