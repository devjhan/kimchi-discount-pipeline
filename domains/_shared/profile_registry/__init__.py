"""domains/_shared/profile_registry — 종목별 Enrich-Cutoff 프로파일 Contract (공유 커널).

정책/메커니즘 분리 마이그레이션의 SSoT 계층. ≥2 도메인(universe Stage 1 +
screener Stage 2)이 소비하는 Contract 이므로 ``_shared/time/`` 와 동일 tier 에 둔다.

- ``schema.EnrichCutoffProfile`` — 종목별 ``required_enrichments`` + ``cutoff_rules``
  (screener Rule dict-tree) + ``Provenance``. frozen + ``__post_init__`` shape 검증.
- ``serde`` — dict ↔ dataclass. on-disk YAML 헤더 컨벤션(schema/version/description).
- ``registry.ProfileRegistry`` — versioned read + injected-writer commit. root 주입.

drift 비교(``compute_drift``)는 policy 단독 소비 + screener rule-tree 지식이라 본 공유
커널이 아니라 ``domains/policy/domain/drift.py`` 가 소유한다 (rule-of-three 미충족).

레이어 정책 (``domains/_shared/__init__.py`` 계승):
- ``infrastructure`` import 금지 — path helper / ``write_output_safely`` 는 caller
  (consumer 의 ``_boundary``)가 주입. 본 패키지는 YAML 읽기에 stdlib ``yaml`` 만 사용.
- 다른 도메인(screener / universe / policy) import 금지 — 본 패키지가 그들의 의존.

⚠️ ``domains/policy/`` (정책 *저작* LLM producer) 와 혼동 금지. 본 패키지는 그
산출물의 *계약/저장소* 일 뿐 정책을 만들지 않는다. ``governance/`` (선언적 정책
specs/config) 와도 다름.
"""
from __future__ import annotations
