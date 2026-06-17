"""
infrastructure/llm/claude_code_deepseek.py — `claude -p` harness + DeepSeek 백엔드 (ADR-0016).

``ClaudeCliAdapter`` 를 상속해 `claude` agentic harness(도구·파일·다단계 루프)는 그대로
재사용하되, ``ANTHROPIC_*`` 환경변수를 DeepSeek 의 Anthropic-호환 엔드포인트로 주입한다.

- 추론·과금은 DeepSeek (기존 ``DEEPSEEK_API_KEY`` 재사용 — 신규 secret 0).
- Anthropic 은 호출되지 않음: 자식 env 에서 ``ANTHROPIC_API_KEY`` 제거 + ``ANTHROPIC_AUTH_TOKEN``
  만 사용 → Anthropic $0 보장 + 인증 충돌(anthropics/claude-code#67861) 차단.
- ``base_url`` / ``auth_token`` 은 강제(override 불가). 모델/effort 는 기본값 주입하되
  사용자 env override 허용.

vendor 종속을 본 bounded adapter 한 곳에 가둔다 (D-CORE-7). headless 호출은 슬래시 커맨드/
Agent SDK 가 아니라 explicit-path 지시문 프롬프트로 수행한다 (run_daily_local.sh).
"""
from __future__ import annotations

import os

from infrastructure._common.utils import load_env_file
from infrastructure.llm.adapter import LlmResult
from infrastructure.llm.claude_cli import ClaudeCliAdapter

# DeepSeek Anthropic-호환 엔드포인트 (공식 문서).
_DEEPSEEK_ANTHROPIC_BASE_URL = "https://api.deepseek.com/anthropic"

# DeepSeek × Claude Code 권장 모델/effort 매핑 (공식 문서). env override 허용.
_MODEL_ENV_DEFAULTS: dict[str, str] = {
    "ANTHROPIC_MODEL": "deepseek-v4-pro[1m]",
    "ANTHROPIC_DEFAULT_OPUS_MODEL": "deepseek-v4-pro[1m]",
    "ANTHROPIC_DEFAULT_SONNET_MODEL": "deepseek-v4-pro[1m]",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL": "deepseek-v4-flash",
    "CLAUDE_CODE_SUBAGENT_MODEL": "deepseek-v4-flash",
    "CLAUDE_CODE_EFFORT_LEVEL": "max",
}


class DeepSeekClaudeCodeAdapter(ClaudeCliAdapter):
    """`claude` harness 를 DeepSeek Anthropic-호환 백엔드로 redirect 하는 adapter."""

    name = "claude-cli-deepseek"

    def __init__(self, binary: str | None = None, token: str | None = None) -> None:
        super().__init__(binary=binary)
        # token 명시(테스트용) 안 하면 .env 의 DEEPSEEK_API_KEY 를 load_env_file 로 해석.
        self._token_override = token

    def _resolve_token(self) -> str:
        if self._token_override is not None:
            return self._token_override.strip()
        return load_env_file().get("DEEPSEEK_API_KEY", "").strip()

    def invoke(
        self,
        prompt: str,
        *,
        allowed_tools: str = "",
        dry_run: bool = False,
    ) -> LlmResult:
        if not self._resolve_token():
            return LlmResult(
                vendor=self.name,
                status="skipped",
                skip_reason="DEEPSEEK_API_KEY 미설정 — .env 에 키를 추가해 주세요 (claude-cli-deepseek)",
            )
        # binary 해석 / cmd 조립 / 실행은 부모 — env 주입만 _subprocess_env override 로.
        return super().invoke(prompt, allowed_tools=allowed_tools, dry_run=dry_run)

    def _subprocess_env(self) -> dict[str, str]:
        """`claude` 서브프로세스 env — DeepSeek Anthropic-호환 백엔드로 redirect.

        token 값은 cmd/로그에 노출되지 않고 오직 자식 프로세스 env 로만 전달된다 (G21).
        """
        env = os.environ.copy()
        # Anthropic 직결 차단 — API key 제거(우발 과금/인증 충돌 방지), AUTH_TOKEN 만 사용.
        env.pop("ANTHROPIC_API_KEY", None)
        # 강제 (override 불가) — Anthropic $0 보장의 핵심.
        env["ANTHROPIC_BASE_URL"] = _DEEPSEEK_ANTHROPIC_BASE_URL
        env["ANTHROPIC_AUTH_TOKEN"] = self._resolve_token()
        # 모델/effort 기본값 — 사용자 env 가 이미 설정했으면 존중(override).
        for key, default in _MODEL_ENV_DEFAULTS.items():
            env.setdefault(key, default)
        return env


__all__ = ["DeepSeekClaudeCodeAdapter"]
