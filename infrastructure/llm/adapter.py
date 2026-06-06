"""
infrastructure/llm/adapter.py — LlmAdapter ABC.

LLM 호출(현재 `claude -p` CLI)의 vendor-neutral seam. `infrastructure/notify` 의
NotifierAdapter 와 동형 — vendor 교체 = adapter 1 클래스 추가 + REGISTRY 한 줄.

**경고 (F-13).** `claude -p "/skill"` 은 single completion 이 아니라 **agentic loop**
(도구·파일·다단계). 따라서 adapter 는 raw model API 한 방이 아니라 *agentic 런타임*을
감싼다. 대체 vendor 도 agentic harness 여야 한다 — 현실 타깃은 "swap 을 bounded
adapter 작업으로", "지금 vendor-free" 가 아니다.

책임 분리: adapter 는 LLM 런타임 실행만. 입력 파일 marshaling / 출력 redirect 는
caller(`run_daily_local.sh`) — notify dispatcher 와 동일 (G6/G9 책임 분리).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class LlmResult:
    """LLM 호출 결과.

    status:
        'completed' — 런타임이 실행 완료 (returncode 로 성공/실패 판정)
        'skipped'   — 런타임 부재 (예: claude CLI 없음) — caller graceful skip
        'dry_run'   — dry_run 모드, 실행 없이 cmd 만 반환
        'error'     — 실행 자체 실패 (spawn 불가 등)
    """

    vendor: str
    status: str
    cmd: list[str] = field(default_factory=list)
    returncode: int | None = None
    skip_reason: str | None = None
    error: str | None = None


class LlmAdapter(ABC):
    """모든 LLM 런타임 vendor 의 base class.

    Subclass MUST set ``name`` (registry key, 예: "claude-cli").
    """

    name: str = ""

    @abstractmethod
    def invoke(
        self,
        prompt: str,
        *,
        allowed_tools: str = "",
        dry_run: bool = False,
    ) -> LlmResult:
        """``prompt`` (skill slash-command 또는 ad-hoc 지시) 를 LLM 런타임에 실행.

        ``allowed_tools`` 는 런타임 tool whitelist (CSV — MCP tool UUID 포함 가능).
        stdout/stderr 는 caller 가 redirect 하도록 inherit (별도 capture 안 함).
        """


__all__ = ["LlmResult", "LlmAdapter"]
