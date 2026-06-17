"""
infrastructure/llm/claude_cli.py — `claude -p` CLI adapter.

현재 파이프라인의 유일한 LLM 런타임. ``run_daily_local.sh`` 에 흩어져 있던
``command -v claude`` 해석 + ``claude -p "<prompt>" --allowed-tools ...`` 조립을
본 adapter 로 중앙화 (F-13 T1). stdout/stderr 는 inherit — caller 의 phase-log
redirect 가 그대로 캡처.
"""
from __future__ import annotations

import shutil
import subprocess

from infrastructure.llm.adapter import LlmAdapter, LlmResult


class ClaudeCliAdapter(LlmAdapter):
    name = "claude-cli"

    def __init__(self, binary: str | None = None) -> None:
        # binary 명시 안 하면 PATH 에서 해석 (bash `command -v claude` 와 동치).
        self._binary = binary or shutil.which("claude")

    def _subprocess_env(self) -> dict[str, str] | None:
        """``claude`` 서브프로세스에 넘길 환경.

        기본 ``None`` → 부모 프로세스 env 그대로 상속 (기존 동작 불변).
        backend redirect 가 필요한 subclass (예: DeepSeek Anthropic-호환) 가
        override 해 ANTHROPIC_* 등을 주입한다 (vendor 종속을 bounded adapter 에
        가둠 — D-CORE-7).
        """
        return None

    def invoke(
        self,
        prompt: str,
        *,
        allowed_tools: str = "",
        dry_run: bool = False,
    ) -> LlmResult:
        if not self._binary:
            return LlmResult(
                vendor=self.name,
                status="skipped",
                skip_reason="claude CLI 부재 — headless LLM stage skip (사용자 환경 의존)",
            )
        cmd = [self._binary, "-p", prompt]
        if allowed_tools:
            cmd += ["--allowed-tools", allowed_tools]

        if dry_run:
            return LlmResult(vendor=self.name, status="dry_run", cmd=cmd)

        try:
            # stdout/stderr inherit → caller (run_daily_local.sh) 의 `>> phase_log 2>&1`
            # redirect 가 claude agentic loop 출력을 그대로 캡처.
            # env=None 이면 부모 env 상속 (기본); subclass 가 backend redirect 주입.
            proc = subprocess.run(cmd, env=self._subprocess_env())  # noqa: S603 — bounded internal cmd
        except Exception as exc:  # noqa: BLE001 — spawn 실패 graceful
            return LlmResult(
                vendor=self.name, status="error", cmd=cmd, error=str(exc)
            )
        return LlmResult(
            vendor=self.name, status="completed", cmd=cmd, returncode=proc.returncode
        )


__all__ = ["ClaudeCliAdapter"]
