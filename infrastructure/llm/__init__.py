"""
infrastructure/llm — LLM 런타임 호출 단일 port (F-13).

`claude -p` 오케스트레이션을 `infrastructure/notify` 의 dispatcher+adapter 패턴으로
중앙화. 활성 vendor = REGISTRY 의 key. ``dispatcher`` 는 ``LLM_VENDOR`` env (기본
"claude-cli") 로 adapter 선택. vendor 교체 = adapter 1 클래스 + 다음 2 라인:

    from infrastructure.llm.openai_agent import OpenAiAgentAdapter
    REGISTRY["openai-agent"] = OpenAiAgentAdapter

종속 진단(F-13): Anthropic SDK/API 종속 0 — 종속은 (C)런타임(`claude -p` CLI) 한 층뿐.
모델명(opus/sonnet/haiku) 하드코딩 무. JSON schema envelope(D-Q-2)가 LLM↔결정론 seam.
"""
from __future__ import annotations

from infrastructure.llm.adapter import LlmAdapter, LlmResult
from infrastructure.llm.claude_cli import ClaudeCliAdapter

REGISTRY: dict[str, type[LlmAdapter]] = {
    ClaudeCliAdapter.name: ClaudeCliAdapter,
}

__all__ = ["REGISTRY", "LlmAdapter", "LlmResult", "ClaudeCliAdapter"]
