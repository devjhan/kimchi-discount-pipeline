"""UniverseEntry — 단일 universe 후보 종목 frozen value object.

원래 ``domains/alpha_factory/universe.py:58-66`` 에 mutable ``@dataclass`` 로
정의되어 있던 객체를 Run 1 에서 frozen 으로 본 모듈에 신설. 기존 mutable 버전은
Run 4 deprecation 까지 alpha_factory.universe 내부에 잔존 (parity validation 위해
동시 가동).

설계 원칙:
- ``frozen=True`` — 한 번 만들어진 entry 는 변경 불가. enrichment 는 별도
  ``EnrichedEntry`` (Run 5) 객체로 wrap.
- ``metadata`` 는 ``Mapping[str, Any]`` 타입 hint 로 read-only intent 표명. dict
  자체는 mutable 이지만 caller 는 immutable 으로 취급할 것.
- ``source_citation`` 은 G7 형식 (`{SOURCE}@{ISO_KST}={VALUE}`) — caller 가 만들어
  넘김. 검증은 ``audit/citation.py`` 책임 (Run 6).
- ``fetched_at`` 은 ISO8601 KST. 본 entry 가 *언제* 발견되었는지 추적. ``AsOfClock``
  과 다름 — clock 은 시점 기준이고 fetched_at 은 fetch 시각.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class UniverseEntry:
    """단일 universe 후보. source 가 fan-in 으로 emit."""

    ticker: str
    """한국 종목 표준 표기: ``KR:{6자리 stock_code}`` (예: KR:003550)."""

    name: str
    """공시 상의 회사명 (한글)."""

    source_category: str
    """발견 카테고리 — enricher 의 ``applies_to`` 매칭 키.

    표준 값 (Run 2~5 추가):
    - ``manual_addition`` — 사용자 명시 추가
    - ``holding_company`` — 지주사 (NAV 할인 enricher attach)
    - ``treasury_action`` — 자사주 취득/소각 (Run 3)
    - ``spin_off_or_merger`` — 분할/합병 (Run 3)
    - ``activist_filing`` — 5% 대량보유 공시 (Run 3)
    - ``preferred_share_pair`` — 우선주 짝 (spread enricher attach, Run 5)
    """

    inclusion_reason: str
    """1줄 human-readable 사유 (브리프 본문에 직접 표시)."""

    fetched_at: str
    """ISO8601 KST timestamp — 본 entry 가 발견된 시각 (AsOfClock 과 별개)."""

    source_citation: str
    """G7 형식 citation: ``{SOURCE}@{ISO_KST}={VALUE}``."""

    metadata: Mapping[str, Any] = field(default_factory=dict)
    """source-specific 부가 정보 (예: filer_name, kind, rcept_no). read-only intent."""
