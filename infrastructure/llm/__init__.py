"""
infrastructure/llm — LLM 런타임 호출 단일 port (F-13).

선호 vendor (``LLM_VENDOR`` env, 기본 "claude-cli-deepseek") 로 adapter 선택.
vendor 교체 = adapter 1 클래스 추가 + REGISTRY 1 줄:

    from infrastructure.llm.vendor_x import VendorXAdapter
    REGISTRY["vendor-x"] = VendorXAdapter

vendor (ADR-0016):
- ``claude-cli-deepseek`` (기본): `claude` agentic harness + DeepSeek Anthropic-호환
  백엔드. Anthropic $0 (추론·과금은 DeepSeek, ``DEEPSEEK_API_KEY`` 재사용).
- ``claude-cli`` (rollback): 순수 Anthropic 백엔드 `claude -p` (Anthropic 과금).

skill 은 single completion 이 아니라 agentic loop (도구·파일·다단계) — raw model API 로
대체 불가, 대체 vendor 도 agentic harness 여야 한다 (D-CORE-7).
JSON schema envelope(D-Q-2)가 LLM ↔ 결정론 seam.
"""

from __future__ import annotations

from infrastructure.llm.adapter import LlmAdapter, LlmResult
from infrastructure.llm.claude_cli import ClaudeCliAdapter
from infrastructure.llm.claude_code_deepseek import DeepSeekClaudeCodeAdapter

REGISTRY: dict[str, type[LlmAdapter]] = {
    DeepSeekClaudeCodeAdapter.name: DeepSeekClaudeCodeAdapter,
    ClaudeCliAdapter.name: ClaudeCliAdapter,
}

__all__ = [
    "REGISTRY",
    "LlmAdapter",
    "LlmResult",
    "ClaudeCliAdapter",
    "DeepSeekClaudeCodeAdapter",
]
