#!/usr/bin/env python3
"""Stage 5 — Sizing Recommendation (thin CLI delegator, F-8 BC layering).

로직은 두 layer 로 분리:
- ``domain/sizing.py``      — 순수 규칙 (SizeRecommendation / Kelly·asymmetry 산수 /
                              per-position·drawdown guard). IO 0.
- ``application/sizing.py`` — orchestration + IO (입력 로드 / envelope / write).

본 모듈은 ``python -m domains.risk_engine.sizing`` 진입점 + 공개 심볼 re-export
(하위호환 / 테스트). LLM 미사용 (G6), 매매 명령 미출력 (G9).
"""
from __future__ import annotations

import sys

from domains.risk_engine.application.sizing import (
    SCHEMA_VERSION,
    STAGE_NAME,
    _load_macro_regime,
    _load_thesis_candidates,
    _portfolio_context_from_yaml,
    main,
)
from domains.risk_engine.domain.sizing import (
    PCT_RE,
    SizeRecommendation,
    apply_portfolio_kelly_cap,
    compute_fractional_kelly,
    extract_asymmetry_ratio,
    parse_pct,
    size_one,
)

__all__ = [
    "SCHEMA_VERSION",
    "STAGE_NAME",
    "PCT_RE",
    "SizeRecommendation",
    "parse_pct",
    "extract_asymmetry_ratio",
    "compute_fractional_kelly",
    "size_one",
    "apply_portfolio_kelly_cap",
    "main",
    "_load_thesis_candidates",
    "_load_macro_regime",
    "_portfolio_context_from_yaml",
]


if __name__ == "__main__":
    sys.exit(main())
