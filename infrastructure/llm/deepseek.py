"""
infrastructure/llm/deepseek.py — DeepSeek Chat API adapter (F-13 vendor swap).

``LLM_VENDOR=deepseek`` 로 활성화. DeepSeek API (api.deepseek.com, OpenAI-compatible)
를 호출해 prompt 를 실행한다. ``claude -p`` 의 agentic loop 와 달리 single-turn chat
completion 이므로, caller 가 필요한 컨텍스트(파일 내용, skill 본문)를 prompt 에 포함해
전달해야 한다.

API 키는 ``DEEPSEEK_API_KEY`` env 에서 읽는다 (``.env`` 에서 load_env_file() 이 주입
가정 — dispatcher 호출 전에 로드 완료되어 있어야 함).

subprocess 대신 ``openai`` Python SDK 사용 — retry / timeout / error handling 내장.
"""

from __future__ import annotations

import os
import sys

from infrastructure.llm.adapter import LlmAdapter, LlmResult

try:
    from openai import OpenAI as _OpenAI
except ImportError:  # noqa: F841 — graceful skip at runtime, not import time
    _OpenAI = None  # type: ignore[assignment]


# 모델 ID — DeepSeek 권장 모델 (최신 stable).
_DEFAULT_MODEL = "deepseek-v4-pro"


class DeepSeekAdapter(LlmAdapter):
    """DeepSeek Chat completion API adapter.

    ``allowed_tools`` — DeepSeek API 에서는 function calling 의 tool 정의로
    해석된다. 빈 문자열이면 tool 없이 plain completion.
    dry_run 모드에서는 API 호출 없이 요청 예시만 stdout 출력 후 종료.
    """

    name = "deepseek"

    def __init__(
        self, api_key: str | None = None, base_url: str = "https://api.deepseek.com"
    ) -> None:
        self._api_key = api_key or os.environ.get("DEEPSEEK_API_KEY", "")
        self._base_url = base_url

    def invoke(
        self,
        prompt: str,
        *,
        allowed_tools: str = "",
        dry_run: bool = False,
    ) -> LlmResult:
        if not self._api_key:
            return LlmResult(
                vendor=self.name,
                status="skipped",
                skip_reason="DEEPSEEK_API_KEY 미설정 — .env 에 키를 추가해 주세요",
            )

        model = self._resolve_model()

        if dry_run:
            info = (
                f"[deepseek] dry_run — vendor={self.name} model={model}\n"
                f"[deepseek] prompt preview (first 200 chars): {prompt[:200]}\n"
                f"[deepseek] prompt length={len(prompt)} allowed_tools={allowed_tools!r}\n"
                f"[deepseek] base_url={self._base_url}\n"
                f"[deepseek] full call:\n"
                f"  POST {self._base_url}/v1/chat/completions\n"
                f"  model={model}\n"
                f"  messages=[system + user prompt ({len(prompt)} chars)]\n"
                f"  tools=({len(allowed_tools.split(',')) if allowed_tools else 0} definitions)\n"
            )
            print(info, end="", file=sys.stderr)
            return LlmResult(
                vendor=self.name,
                status="dry_run",
                cmd=["openai", "POST", f"{self._base_url}/v1/chat/completions", model],
            )

        if _OpenAI is None:
            return LlmResult(
                vendor=self.name,
                status="error",
                error="openai Python package 미설치 — `pip install openai` 실행 필요",
            )

        try:
            client = _OpenAI(api_key=self._api_key, base_url=self._base_url)

            messages: list[dict[str, str]] = [
                {
                    "role": "system",
                    "content": "You are an investment research assistant. Follow the instructions precisely. Output in Korean unless specified otherwise.",
                },
                {"role": "user", "content": prompt},
            ]

            kwargs: dict = {
                "model": model,
                "messages": messages,
                "stream": False,
            }

            # allowed_tools 가 있으면 function calling tool 정의로 전환.
            # comma-separated tool name list → 간단한 tool 정의 변환.
            if allowed_tools:
                tools = _build_tools(allowed_tools)
                if tools:
                    kwargs["tools"] = tools

            response = client.chat.completions.create(**kwargs)

            content = response.choices[0].message.content or ""
            print(content, end="")

            return LlmResult(
                vendor=self.name,
                status="completed",
                returncode=0,
                cmd=[model, f"{len(content)} chars"],
            )

        except Exception as exc:  # noqa: BLE001 — 모든 API 예외 graceful 처리
            return LlmResult(
                vendor=self.name,
                status="error",
                error=f"DeepSeek API 호출 실패: {exc}",
            )

    @staticmethod
    def _resolve_model() -> str:
        """모델 선택: ``DEEPSEEK_MODEL`` env → ``_DEFAULT_MODEL`` fallback."""
        return os.environ.get("DEEPSEEK_MODEL", _DEFAULT_MODEL)


def _build_tools(allowed_tools_csv: str) -> list[dict]:
    """``allowed_tools`` CSV 를 DeepSeek function calling tool 정의 list 로 변환.

    ``claude -p`` 의 ``--allowed-tools`` 호환성을 위한 최소 변환.
    DeepSeek API 는 실제 tool execution 을 하지 않으므로, 단순히 사용 가능한
    행동 영역을 system prompt 에 전달하는 용도.
    """
    tool_names = [t.strip() for t in allowed_tools_csv.split(",") if t.strip()]
    if not tool_names:
        return []

    # 최소 tool 정의: 각 tool name 을 function definition 의 description 으로 감쌈.
    # 실제 function calling 실행은 하지 않고, LLM 이 참고용으로만 사용.
    return [
        {
            "type": "function",
            "function": {
                "name": _sanitize_tool_name(name),
                "description": f"Allows using the {name} capability/tool in the environment.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "description": f"The action to perform using {name}.",
                        }
                    },
                    "required": ["action"],
                },
            },
        }
        for name in tool_names
    ]


def _sanitize_tool_name(name: str) -> str:
    """function calling name 은 영숫자+밑줄+하이픈만 허용.

    MCP UUID 포함된 tool name (예: ``mcp__bb9a3bd8-...__slack_send_message``) 은
    ``__`` 를 ``_`` 로 치환.
    """
    import re

    sanitized = re.sub(r"[^a-zA-Z0-9_-]", "_", name)
    # 연속 __ → _ (function name 은 연속 특수문자 비권장)
    while "__" in sanitized:
        sanitized = sanitized.replace("__", "_")
    return sanitized.strip("_")


__all__ = ["DeepSeekAdapter"]
