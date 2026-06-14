"""domains/_shared/external_signal — external signal ingest 산출물 schema validator.

``/ingest-external-signal`` 스킬이 ``telemetry/external_signals/{ticker}/{date}-{seq}.md``
로 산출하는 fact-only redacted signal 파일의 결정론적 검증 게이트. 산출/소비가 모두
LLM 스킬뿐이라 부재했던 deterministic guard 를 보강한다 (daily_pipeline Stage 4 소비 전).

검사 항목:
- A: frontmatter 필수키 / 타입 / ticker 형식 / type enum
- B: 필수 섹션 (``## Fact`` / ``## Original``)
- C: G7 citation 형식 (``{source}@{ts}={value}``) — CITATION_RE SSoT 재사용
- D: G20 파일명 규약 (``{date}-{seq:03d}.md``) + observed_at date 일치

레이어: 코어 ``validate.py`` 는 ``Path`` 만 받아 infra/도메인 무의존 (순수). 디렉토리
스캔이 필요한 CLI(``__main__``)·게이트만 ``infrastructure._common.utils`` import
(_shared 의 platform-utility import 허용 범위, ``_shared/__init__`` 정책).
"""

from __future__ import annotations

from domains._shared.external_signal.validate import (
    ValidationResult,
    validate_signal_file,
)

__all__ = ["ValidationResult", "validate_signal_file"]
