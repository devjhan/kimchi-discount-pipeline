"""PositionThesis — 보유 포지션의 machine-state(falsifier spec) frozen value object.

stage4-thesis-auditor(+ 사용자)가 *저작*하고 risk_engine 의 일별 monitor
(falsifier_proximity / thesis_expiry_monitor / event_falsifier_linker)가 *기계적으로
소비*한다. 본 모듈은 thesis.json 의 shape 만 검증 — falsifier ``spec`` 의 *내용*
(metric / target_value / direction / watch_catalyst_type 등)은 절대 검증하지 않는다.
spec 의미의 단일 권위는 각 monitor (profile_registry 의 cutoff_rules ↔ RuleFactory 와 동형).

**검증 관용도 (가장 중요한 제약).** profile_registry 와 달리 monitor 들은 의도적으로
graceful 하다 — horizon/entry_date 누락은 crash 가 아니라 ``unmeasurable`` 로 처리.
따라서 ``__post_init__`` 은 **malformed ticker / unknown falsifier category 에만 raise**
하고, 누락 ``time_horizon_months`` / ``entry_date`` / ``entry_price_krw`` 는 tolerate 한다.
over-strict 검증은 오늘의 graceful ``unmeasurable`` 레코드를 hard crash 로 바꿔 e2e 를
깨뜨린다.

스토어 계약 SSoT: ``telemetry/positions/README.md`` §3.
하우스 스타일: frozen dataclass + ``__post_init__`` 수동 검증 (Pydantic 아님).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from domains._shared.positions_store.errors import PositionSchemaError

SCHEMA_VERSION = "positions-thesis-v1"
"""thesis.json on-disk ``schema`` 키 값. schema-less dict(레거시/수기 fixture)는
serde 가 'v1 unversioned' 로 수용. 호환 깨질 때만 bump → serde.from_dict 가 reject."""

FALSIFIER_CATEGORIES = ("time_cap", "metric_trigger", "event_trigger")
"""README §3 + stage4 falsifier 카테고리. monitor 들이 분기하는 단일 enum."""


@dataclass(frozen=True)
class FalsifierSpec:
    """반증 trigger 한 건. ``spec`` 은 카테고리별 키를 담은 opaque passthrough."""

    category: str
    """FALSIFIER_CATEGORIES 중 하나."""

    spec: Mapping[str, Any] = field(default_factory=dict)
    """카테고리별 schema (metric_trigger: metric/target_value/direction, ...).
    내용은 검증 안 함 — monitor 가 단독 해석."""

    def __post_init__(self) -> None:
        if self.category not in FALSIFIER_CATEGORIES:
            raise PositionSchemaError(
                f"falsifier.category 는 {FALSIFIER_CATEGORIES} 중 하나: {self.category!r}"
            )
        if not isinstance(self.spec, Mapping):
            raise PositionSchemaError(f"falsifier.spec 는 Mapping: {type(self.spec).__name__}")


@dataclass(frozen=True)
class ThesisProvenance:
    """thesis.json 을 누가/무엇으로부터 commit 했나. ``citations`` 는 G7 형식."""

    committed_at: str = ""
    """now_iso_kst() — commit 시각 (ISO8601 + KST)."""

    committed_by: str = ""
    """"stage4-derive" | "manual" | "regression-fixture"."""

    source: str = ""
    """"04-thesis-candidates.json#candidates[i]" | "manual" — 파생 출처."""

    citations: tuple[str, ...] = ()
    """G7 형식 evidence — stage4 asymmetry citation carry."""

    rationale_ko: str = ""
    """1줄 한국어 의도."""


@dataclass(frozen=True)
class PositionThesis:
    """단일 포지션의 machine state. risk_engine monitor 가 일별 소비.

    필드는 3 monitor + sizing 이 실제 파싱하는 것에서 역도출 (README §3 shape).
    """

    ticker: str
    """"KR:NNNNNN" 형식."""

    name: str = ""
    falsifier: FalsifierSpec = field(
        default_factory=lambda: FalsifierSpec(category="time_cap")
    )
    entry_date: str = ""
    """"YYYY-MM-DD". 누락 tolerate — monitor 가 unmeasurable 처리."""

    time_horizon_months: float | None = None
    """누락/None tolerate."""

    edge_source: tuple[str, ...] = ()
    entry_price_krw: float | None = None
    """진입가. 사용자 진입 전엔 None (monitor tolerate)."""

    status: str = "open"
    """"open" | "closed" | ... — 누락 시 open 취급(monitor 와 동일)."""

    entry_catalyst: str = ""
    asymmetry_score: Mapping[str, Any] = field(default_factory=dict)
    provenance: ThesisProvenance = field(default_factory=ThesisProvenance)

    def __post_init__(self) -> None:
        # 하우스 스타일: 수동 검증. malformed ticker / unknown category 에만 raise —
        # 그 외(누락 horizon/date/price)는 monitor 가 graceful 처리하므로 tolerate.
        if not self.ticker or ":" not in self.ticker:
            raise PositionSchemaError(f"ticker 는 'KR:NNNNNN' 형식: {self.ticker!r}")
        if not isinstance(self.falsifier, FalsifierSpec):
            raise PositionSchemaError("falsifier 는 FalsifierSpec 인스턴스")
