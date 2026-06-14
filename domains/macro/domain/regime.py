"""RegimeResult / IndicatorResult — Stage 0 산출 frozen value objects."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class IndicatorResult:
    """단일 indicator 의 값 + 라벨 + citation.

    legacy ``macro_regime.py`` 의 dict 표현을 type-safe 하게 wrap.
    main.py 가 envelope 으로 serialize 시 ``asdict()`` 사용.
    """

    indicator: str
    """human-readable indicator 정의 (예: 'US10Y - US2Y')."""

    value: float | None
    """결정적 측정값 (skip 시 None)."""

    value_label: str
    """human-readable label ('inverted' / 'tight' / 'complacent' / 'unknown' 등)."""

    source_citation: str | None
    """G7 형식 citation (skip 시 None)."""

    skip_reason: str | None = None
    """non-None 이면 indicator 수집 실패 (FRED key 부재 / fetch fail 등)."""

    percentile: float | None = None
    """VIX 같은 percentile 기반 indicator 만 사용 (0.0~1.0)."""


@dataclass(frozen=True)
class RegimeResult:
    """classify_regime() 의 산출 — main.py 가 envelope 으로 직렬화."""

    regime: str
    """early_cycle | mid_cycle | late_cycle | crisis | unknown."""

    rationale: tuple[str, ...]
    """votes 의 각 indicator 별 근거 (human-readable)."""

    votes: tuple[str, ...]
    """각 indicator 가 던진 vote (skip 된 indicator 는 미포함)."""

    vote_summary: dict[str, int] = field(default_factory=dict)
    """{vote: count} — envelope 의 ``vote_summary`` 필드."""
