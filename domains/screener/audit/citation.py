"""G7 citation 검증 — ``domains/_shared/audit/citation`` 재export (back-compat).

``CITATION_RE`` SSoT 는 공유 커널에. 기존 import 경로
(``from domains.screener.audit.citation import is_valid_citation``) 보존용 thin
re-export.
"""
from __future__ import annotations

from domains._shared.audit.citation import (
    CITATION_RE,
    filter_valid_citations,
    is_valid_citation,
)

__all__ = ["CITATION_RE", "filter_valid_citations", "is_valid_citation"]
