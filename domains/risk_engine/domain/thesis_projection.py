"""Stage 5a thesis-sync 의 순수 projection 규칙 (schema bridge).

F-8: stage4 falsifier shape `{categories[], items[]}` → monitor 가 읽는 단일
`{category, spec}` projection. 본 모듈은 **순수** — IO / `_boundary` / 시계 접근 0
(``project_thesis`` 는 ``now_iso_kst`` 시계 read 때문에 application 에 남김).
``domains._shared.positions_store.schema`` 는 shared kernel (DDD 예외).

Hard guards: G6 (projection 결정론, LLM 위임 금지).
"""
from __future__ import annotations

from typing import Any

from domains._shared.positions_store.schema import FALSIFIER_CATEGORIES, FalsifierSpec


def project_edge_source(edge_source: Any) -> tuple[str, ...]:
    """stage4 edge_source(`{primary: [...]}` 또는 list) → reader list."""
    if isinstance(edge_source, dict):
        return tuple(edge_source.get("primary") or ())
    if isinstance(edge_source, (list, tuple)):
        return tuple(edge_source)
    return ()


def project_spec(category: str, item: dict[str, Any]) -> dict[str, Any]:
    """stage4 falsifier item → monitor 가 읽는 카테고리별 spec dict."""
    statement = item.get("statement") or ""
    spec: dict[str, Any] = {}
    if category == "time_cap":
        # horizon 은 thesis.time_horizon_months 가 carry — spec 엔 보조 정보만.
        if item.get("max_months") is not None:
            spec["max_months"] = item["max_months"]
    elif category == "metric_trigger":
        if item.get("metric") is not None:
            spec["metric"] = item["metric"]
        if item.get("threshold") is not None:
            spec["target_value"] = item["threshold"]  # threshold → target_value 매핑
        if item.get("direction") is not None:
            spec["direction"] = item["direction"]
        if item.get("baseline_value") is not None:
            spec["baseline_value"] = item["baseline_value"]
    elif category == "event_trigger":
        if item.get("watch_catalyst_type") is not None:
            spec["watch_catalyst_type"] = item["watch_catalyst_type"]
        if item.get("direction") is not None:
            spec["direction"] = item["direction"]
        spec["description"] = item.get("description") or statement
    if statement and category != "event_trigger":
        spec["statement"] = statement
    return spec


def project_falsifier(
    falsifier: dict[str, Any],
) -> tuple[FalsifierSpec, list[str]]:
    """stage4 falsifier `{categories, items}` → 단일 FalsifierSpec(primary) + warnings."""
    warnings: list[str] = []
    items = list(falsifier.get("items") or [])
    categories = list(falsifier.get("categories") or [])
    if not items:
        # items 부재 — categories[0] 또는 time_cap 으로 빈 spec 투영.
        cat = categories[0] if categories else "time_cap"
        if cat not in FALSIFIER_CATEGORIES:
            cat = "time_cap"
        warnings.append("falsifier.items 비어있음 → 빈 spec 투영")
        return FalsifierSpec(category=cat, spec={}), warnings
    primary = items[0]
    cat = primary.get("category") or (categories[0] if categories else "")
    if len(items) > 1:
        warnings.append(
            f"falsifier 다중({len(items)}개) → primary='{cat}' 만 thesis.json 에 투영 "
            "(단일-falsifier reader shape — 나머지는 thesis.md narrative 에만 보존)"
        )
    return FalsifierSpec(category=cat, spec=project_spec(cat, primary)), warnings


def collect_citations(asymmetry: dict[str, Any]) -> tuple[str, ...]:
    """asymmetry downside/upside 의 G7 source_citation carry."""
    cites: list[str] = []
    for key in ("downside_floor", "upside_ceiling"):
        sec = (asymmetry or {}).get(key) or {}
        c = sec.get("source_citation")
        if c:
            cites.append(str(c))
    return tuple(cites)
