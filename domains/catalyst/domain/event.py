"""CatalystEvent — Stage 3 catalyst 검출 산출 값 객체.

구 ``domains/alpha_factory/catalyst_scan.py:CatalystEvent`` 와 **필드 동일·순서 동일**
(``03-catalyst-events.json`` byte 호환 보존). ``frozen=True`` 는 필드 재할당만 막고
``metadata`` dict *내용* 변형 (orchestrator 의 d_type augment / quality_pass marker)
은 허용하므로 기존 mutation 패턴과 호환된다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class CatalystEvent:
    catalyst_id: str
    ticker: str
    name: str
    catalyst_type: str  # treasury_share_cancellation 등 catalyst 키
    trigger_class: str  # 'a_type' | 'b_type' | 'd_type'
    detected_at: str
    source_citation: str
    metadata: dict[str, Any] = field(default_factory=dict)
