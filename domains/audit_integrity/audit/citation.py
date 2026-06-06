"""G7 citation 검증 — ``domains/_shared/audit/citation`` 재export (back-compat)."""
from __future__ import annotations

from domains._shared.audit.citation import (
    CITATION_RE,
    filter_valid_citations,
    is_valid_citation,
)

__all__ = ["CITATION_RE", "filter_valid_citations", "is_valid_citation"]
