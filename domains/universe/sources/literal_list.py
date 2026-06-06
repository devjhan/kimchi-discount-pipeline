"""LiteralListSource — 사용자 명시 ticker 리스트 (manual_additions 직역).

원래 ``domains/alpha_factory/universe.py:521-554`` 의 ``apply_manual_additions``
함수를 Source plugin 패턴으로 이전. 차이점: 함수 → frozen dataclass + YAML config.

config (``config/sources.yaml`` 내 한 entry):
    - type: "literal_list"
      name: "manual_addition"
      items_ref: "manual_additions.yaml"        # 외부 yaml 참조 (권장)
      # 또는
      items: [...]                              # inline (작은 list 한정)
      source_category: "manual_addition"        # default
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from domains.universe import _boundary
from domains.universe.domain.entry import UniverseEntry
from domains.universe.sources.base import DiscoveryContext, DiscoverySource, SourceResult
from domains.universe.sources.registry import register_source


@register_source("literal_list")
@dataclass(frozen=True)
class LiteralListSource(DiscoverySource):
    """config 의 items: 를 그대로 UniverseEntry 로 변환. discovery 로직 없음."""

    name: str
    items: tuple[Any, ...]
    source_category: str = "manual_addition"

    @classmethod
    def from_spec(cls, spec: dict[str, Any]) -> "LiteralListSource":
        items = spec.get("items")
        if items is None:
            ref = spec.get("items_ref")
            if not ref:
                raise ValueError(
                    f"literal_list source '{spec.get('name')}': "
                    "items / items_ref 둘 다 부재"
                )
            loaded = _boundary.load_sub_config(ref)
            items = loaded.get("items") or []
        if not isinstance(items, list):
            raise ValueError(
                f"literal_list source '{spec.get('name')}': items 는 list 이어야 함"
            )
        return cls(
            name=spec["name"],
            items=tuple(items),
            source_category=spec.get("source_category", "manual_addition"),
        )

    def discover(self, ctx: DiscoveryContext) -> SourceResult:
        warnings: list[str] = []
        entries: list[UniverseEntry] = []
        fetched_at = _boundary.now_iso_kst()
        for raw in self.items:
            if isinstance(raw, str):
                ticker, name, reason = raw, raw, "user_manual_addition"
            elif isinstance(raw, Mapping):
                ticker = str(raw.get("ticker") or "").strip()
                name = str(raw.get("name") or ticker).strip()
                reason = str(raw.get("reason") or "user_manual_addition").strip()
            else:
                warnings.append(
                    f"{self.name}: invalid entry skipped — type={type(raw).__name__}"
                )
                continue
            if not ticker:
                warnings.append(f"{self.name}: empty ticker skipped")
                continue
            entries.append(
                UniverseEntry(
                    ticker=ticker,
                    name=name,
                    source_category=self.source_category,
                    inclusion_reason=reason,
                    fetched_at=fetched_at,
                    source_citation=_boundary.format_citation("user", fetched_at, self.name),
                )
            )
        return SourceResult(
            entries=tuple(entries),
            warnings=tuple(warnings),
            degraded=False,
        )
