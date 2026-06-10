"""
infrastructure/llm — LLM 런타임 호출 단일 port (F-13).

선호 vendor (``LLM_VENDOR`` env, 기본 "deepseek") 로 adapter 선택.
vendor 교체 = adapter 1 클래스 추가 + REGISTRY 1 줄:

    from infrastructure.llm.vendor_x import VendorXAdapter
    REGISTRY["vendor-x"] = VendorXAdapter

종속 진단(F-13): DeepSeek API (``openai`` SDK, base_url=api.deepseek.com).
레거시 ``claude-cli`` 도 rollback safety 로 유지.
JSON schema envelope(D-Q-2)가 LLM ↔ 결정론 seam.
"""

from __future__ import annotations

from infrastructure.llm.adapter import LlmAdapter, LlmResult
from infrastructure.llm.claude_cli import ClaudeCliAdapter
from infrastructure.llm.deepseek import DeepSeekAdapter

REGISTRY: dict[str, type[LlmAdapter]] = {
    DeepSeekAdapter.name: DeepSeekAdapter,
    ClaudeCliAdapter.name: ClaudeCliAdapter,
}

__all__ = ["REGISTRY", "LlmAdapter", "LlmResult", "ClaudeCliAdapter", "DeepSeekAdapter"]
