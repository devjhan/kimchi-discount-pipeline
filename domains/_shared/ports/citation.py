"""CitationPort — G7 citation 문자열 포맷 seam (순수 typing, infra import 0).

``{SOURCE}@{ISO_KST}={VALUE}`` (G7) 형식 생성의 단일 계약. 구현(adapter)은 각 BC
``_boundary`` 가 ``infrastructure._common.utils.format_citation`` 에 위임해 구성하며,
application/io 는 본 Protocol 에만 의존한다 (composition root 가 주입).

선례: ``domains/policy/ports/llm.py`` (PolicyEngine) — port=Protocol / adapter=_boundary.
"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class CitationPort(Protocol):
    """G7 형식 citation 문자열 생성 (단일 메서드 port)."""

    def format(self, source: str, ts: str, value: Any) -> str:
        """``{source}@{ts}={value}`` (G7) 반환. ts 는 ISO8601 KST. 부수효과 금지."""
        ...
