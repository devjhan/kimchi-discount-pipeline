"""DisclosureSourcePort — DART 공시 list iteration seam (순수 typing, infra import 0).

``infrastructure.dart.client.iter_disclosures`` (각 BC ``_boundary.dart_iter_disclosures``
가 api_key 바인딩해 노출) 의 형식 계약. ``domains/_shared/adapters/disclosure_scan`` 의
shared scan 이 본 port 에만 의존 → DART/infra import 0 (D-CORE-4 안전). 소비 BC 는
``functools.partial(_boundary.dart_iter_disclosures, api_key)`` 를 주입한다.
"""
from __future__ import annotations

from typing import Any, Iterable, Protocol, runtime_checkable


@runtime_checkable
class DisclosureSourcePort(Protocol):
    """기간 + 공시타입 → DART list item iterable (api_key 는 바인딩 가정)."""

    def __call__(
        self,
        *,
        bgn_de: str,
        end_de: str,
        pblntf_ty: str,
        corp_code: str | None = None,
    ) -> Iterable[dict[str, Any]]:
        """[bgn_de, end_de] 기간의 pblntf_ty 공시 list item 을 yield."""
        ...
