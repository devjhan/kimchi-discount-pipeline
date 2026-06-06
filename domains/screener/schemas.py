"""산출물 / cache envelope schema name 상수.

Stage 3/4/6 + quality-lens skill + audit-shadow 의 5 consumer 가 read 하는
schema name 은 절대 변경 금지. version bump 시 downstream 동시 PR 필요.

cache schema 는 screener 내부 — v3 (legacy alpha_factory) 와 v4 (신규 raw
filing 보관) 양쪽 모두 read 지원. write 는 v4 만.
"""
from __future__ import annotations

from typing import Final

SCHEMA_QUALITY_FILTER: Final[str] = "investment-stage2-quality-filter-v1"
SCHEMA_FIN_FETCH: Final[str] = "investment-stage2-fin-fetch-v3"

# V4: raw FilingMetric (filings[]) + capital_signals_events[] 보관.
# legacy v3 cache 는 schema mismatch 로 cache miss 처리되어 다음 fetch 에서
# v4 로 자동 overwrite. 별도 마이그레이션 스크립트 불필요.
SCHEMA_FIN_CACHE_V4: Final[str] = "investment-stage2-fin-cache-v4"
SCHEMA_FIN_CACHE: Final[str] = SCHEMA_FIN_CACHE_V4
