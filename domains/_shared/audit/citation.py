"""G7 citation 형식 검증 — ``{SOURCE}@{ISO_TIMESTAMP_KST}={VALUE}`` (SSoT).

screener / universe / policy / macro 의 ``audit/citation.py`` + ``brief_gate``
(``validators.py``) 가 각자 정의해 온 ``CITATION_RE`` 의 단일 출처. 패턴 변경 시
본 파일 한 곳만 수정한다 (기존 5곳 동기 수정 → 1곳).

주의: ``.claude/hooks/quality/brief_citation_gate`` 훅의 *본문 substring 스캔*
정규식 (``[A-Za-z0-9_]+@\\S+=\\S+``, anchor 없음) 은 의도적으로 다른 용도라 본
SSoT 와 통합하지 않는다 — 본 모듈은 *문자열 전체* 정합성 검증 (anchored) 용.
"""
from __future__ import annotations

import re

CITATION_RE = re.compile(r"^[A-Za-z0-9_]+@\S+=.+$")


def is_valid_citation(citation: str) -> bool:
    """G7 형식 정합성. 빈 문자열 / None-equivalent 은 False."""
    if not citation:
        return False
    return bool(CITATION_RE.match(citation))


def filter_valid_citations(citations: tuple[str, ...]) -> tuple[str, ...]:
    """G7 형식에 맞는 것만 유지. dedup 보존 순서."""
    seen: set[str] = set()
    out: list[str] = []
    for c in citations:
        if is_valid_citation(c) and c not in seen:
            seen.add(c)
            out.append(c)
    return tuple(out)
