"""EnrichCutoffProfile — 종목별 Enrich-Cutoff 프로파일 frozen value object.

정책/메커니즘 분리의 Contract. policy(producer)가 *저작*하고 universe+screener
(mechanism)가 *기계적으로 소비*한다. 본 모듈은 스키마 shape 만 검증 — ``cutoff_rules``
의 룰 *의미*(metric_path 유효성 / op 등)는 절대 검증하지 않는다. 룰 검증의 단일
권위는 screener ``RuleFactory`` (anchor #1).

ISP 결정 (F-2): universe 는 사실상 ``required_enrichments`` 만, screener 는
``cutoff_rules`` 만 쓰지만 둘 다 본 프로파일 *전체* 에 의존한다. universe-view /
screener-view 로 **쪼개지 않는다** — 프로파일은 enrich+cutoff 를 한 호흡으로 정의하는
**단일 정책 단위**이고, 통째 의존이 그 의도를 정직하게 반영한다 (serde 분할 비용 >
ISP 이득). 두 소비자의 입력-완전성 결합(Completeness Gate)은
``governance/pipeline-overview.md`` §4b 참조.

하우스 스타일: frozen dataclass + ``__post_init__`` 수동 검증 (Pydantic 아님).
저장소 전 도메인 객체가 동일 패턴 — 신규 의존성 0.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from domains._shared.profile_registry.errors import ProfileSchemaError

SCHEMA_VERSION = "policy-profile-v1"
"""ADR-0013 Q2: 통합 scope-tagged 스키마(``policy_profile``)로 수렴 — EnrichCutoffProfile
은 그 **scope=ticker view** 다. on-disk 직렬화/역직렬화는 ``policy_profile.serde`` 단일
권위에 위임한다(``serde.py``). 본 상수는 ``policy_profile.SCHEMA_VERSION`` 과 동일 값
(순환 import 회피 위해 리터럴 중복). bump => 마이그레이션 게이트 reject."""


@dataclass(frozen=True)
class Provenance:
    """policy 가 이 프로파일을 commit 한 근거. ``citations`` 는 G7 형식."""

    committed_at: str
    """now_iso_kst() — commit 시각 (ISO8601 + KST)."""

    committed_by: str
    """"policy" | "manual" | "regression-fixture"."""

    trigger: str
    """"filing:rcept_no=..." | "news:..." | "manual" — 무엇이 이 프로파일을 촉발했나."""

    citations: tuple[str, ...] = ()
    """G7 형식 evidence: "DART@<iso>=<value>"."""

    rationale_ko: str = ""
    """1줄 한국어 의도."""


@dataclass(frozen=True)
class EnrichCutoffProfile:
    """단일 ticker 의 Enrich-Cutoff 프로파일. universe+screener 가 mechanically 소비.

    - ``required_enrichments`` — universe enricher name 집합 (예: "nav_discount").
      빈 tuple 허용 (보강 불요 종목).
    - ``cutoff_rules`` — 기존 screener Rule dict-tree (``{"type": "and", ...}``).
      opaque ``Mapping`` passthrough — 룰 의미는 RuleFactory 가 단독 검증.
    """

    ticker: str
    """"KR:NNNNNN" 형식."""

    schema_version: str
    """== SCHEMA_VERSION."""

    profile_version: int
    """ticker 별 monotonic 정수 (1, 2, 3, ...)."""

    required_enrichments: tuple[str, ...]
    """universe 가 이 종목에 적용할 enricher name 집합."""

    cutoff_rules: Mapping[str, Any]
    """screener Rule dict-tree (RuleFactory 소비). 'type' 키 보유 필수."""

    provenance: Provenance
    """commit 근거 + G7 citations."""

    description: str = ""
    """config-header lint(D-CFG-1) 대응 — on-disk YAML 의 description 미러."""

    def __post_init__(self) -> None:
        # 하우스 스타일: 수동 검증, ProfileSchemaError raise (pydantic 아님).
        if not self.ticker or ":" not in self.ticker:
            raise ProfileSchemaError(f"ticker는 'KR:NNNNNN' 형식: {self.ticker!r}")
        if self.profile_version < 1:
            raise ProfileSchemaError("profile_version >= 1")
        if self.schema_version != SCHEMA_VERSION:
            raise ProfileSchemaError(
                f"schema_version mismatch: {self.schema_version!r} "
                f"(expected {SCHEMA_VERSION!r})"
            )
        if not isinstance(self.cutoff_rules, Mapping) or "type" not in self.cutoff_rules:
            raise ProfileSchemaError("cutoff_rules는 'type' 키를 가진 Rule dict-tree여야 함")
        # NOTE: 룰 의미(metric_path 유효성, op 등)는 여기서 검증하지 않음 — RuleFactory 책임.
