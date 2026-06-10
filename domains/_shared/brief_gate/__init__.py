"""
domains/_shared/brief_gate — Stage 6 schema validators (brief 입력 게이트).

LLM brief 합성 본체는 `.agents/skills/investment-stage6-brief-author` skill 책임.
본 module은 skill 이 brief 산출 전 입력 산출물의 schema / G7 citation
적합성을 fail-fast 검사하기 위한 validator 함수만 export 한다 (순수 read-only 검증,
`_boundary` 없음 — 모든 BC 산출물을 읽는 cross-cutting validator 라 `_shared` 거주).
외부 채널 outbound 발송은 `infrastructure/notify/` 로 분리됨 (F-19 강등: 구 `domains/brief_gate` BC).
"""

from domains._shared.brief_gate.validators import (
    CITATION_RE,
    OPTIONAL_FILES,
    REQUIRED_FILES,
    validate_stage_inputs,
)

__all__ = [
    "validate_stage_inputs",
    "CITATION_RE",
    "REQUIRED_FILES",
    "OPTIONAL_FILES",
]
