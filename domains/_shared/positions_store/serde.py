"""dict ↔ PositionThesis 직렬화/역직렬화.

on-disk thesis.json 형식은 ``telemetry/positions/README.md`` §3 가 못박은 nested shape:
top-level {ticker, name, entry_date, entry_price_krw, status} + ``thesis`` 하위에
{entry_catalyst, falsifier{category, spec}, time_horizon_months, edge_source,
asymmetry_score}. 본 모듈은 거기에 ``schema``(버전 게이트) + ``_provenance``(G7 carry)
두 메타 키를 더한다 — monitor 는 ``.get()`` 접근이라 추가 키를 무시한다.

``from_dict`` 의 schema 게이트는 **profile_registry 와 비대칭**: 기존 fixture / 수기
thesis.json 엔 ``schema`` 키가 없으므로 **schema-less dict 를 'v1 unversioned' 로 수용**
한다. 키가 *있는데* SCHEMA_VERSION 과 다를 때만 reject.
"""
from __future__ import annotations

from typing import Any, Mapping

from domains._shared.positions_store.errors import PositionSchemaError
from domains._shared.positions_store.schema import (
    SCHEMA_VERSION,
    FalsifierSpec,
    PositionThesis,
    ThesisProvenance,
)


def to_dict(t: PositionThesis) -> dict[str, Any]:
    """PositionThesis → on-disk thesis.json dict (README §3 shape + 메타 키)."""
    return {
        "schema": SCHEMA_VERSION,
        "ticker": t.ticker,
        "name": t.name,
        "entry_date": t.entry_date,
        "entry_price_krw": t.entry_price_krw,
        "status": t.status,
        "thesis": {
            "entry_catalyst": t.entry_catalyst,
            "falsifier": {
                "category": t.falsifier.category,
                "spec": dict(t.falsifier.spec),
            },
            "time_horizon_months": t.time_horizon_months,
            "edge_source": list(t.edge_source),
            "asymmetry_score": dict(t.asymmetry_score),
        },
        "_provenance": {
            "committed_at": t.provenance.committed_at,
            "committed_by": t.provenance.committed_by,
            "source": t.provenance.source,
            "citations": list(t.provenance.citations),
            "rationale_ko": t.provenance.rationale_ko,
        },
    }


def from_dict(raw: Mapping[str, Any]) -> PositionThesis:
    """on-disk thesis.json dict → PositionThesis.

    schema-less dict 수용(레거시/fixture). ``schema`` 키가 SCHEMA_VERSION 과 다르면 reject.
    손상/누락 falsifier.category 등은 PositionSchemaError 전파(silent pass 금지).
    """
    sv = raw.get("schema")
    if sv is not None and sv != SCHEMA_VERSION:
        raise PositionSchemaError(
            f"unsupported schema: {sv!r} (expected {SCHEMA_VERSION!r})"
        )
    thesis = raw.get("thesis") or {}
    falsifier = thesis.get("falsifier") or {}
    prov = raw.get("_provenance") or {}
    horizon = thesis.get("time_horizon_months")
    try:
        return PositionThesis(
            ticker=raw["ticker"],
            name=raw.get("name", "") or "",
            falsifier=FalsifierSpec(
                category=falsifier.get("category", ""),
                spec=falsifier.get("spec") or {},
            ),
            entry_date=raw.get("entry_date", "") or "",
            time_horizon_months=(float(horizon) if horizon is not None else None),
            edge_source=tuple(thesis.get("edge_source") or ()),
            entry_price_krw=raw.get("entry_price_krw"),
            status=raw.get("status", "open") or "open",
            entry_catalyst=thesis.get("entry_catalyst", "") or "",
            asymmetry_score=thesis.get("asymmetry_score") or {},
            provenance=ThesisProvenance(
                committed_at=prov.get("committed_at", ""),
                committed_by=prov.get("committed_by", ""),
                source=prov.get("source", ""),
                citations=tuple(prov.get("citations") or ()),
                rationale_ko=prov.get("rationale_ko", ""),
            ),
        )
    except (KeyError, TypeError, ValueError) as exc:
        # FalsifierSpec/__post_init__ 의 PositionSchemaError 는 그대로 통과, 그 외는 wrap.
        raise PositionSchemaError(f"thesis dict 파싱 실패: {exc}") from exc
