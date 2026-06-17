"""tests/unit/test_llm_dispatcher.py — infrastructure/llm port (F-13 / ADR-0016).

Vendor-neutral seam — claude-cli (순수 Anthropic) / claude-cli-deepseek (DeepSeek 백엔드)
adapter 공통 검증. 실제 Network/API/subprocess 호출 없이 (dry-run + monkeypatch + token 주입).
"""

from __future__ import annotations

import pytest

from infrastructure.llm import REGISTRY
from infrastructure.llm.claude_cli import ClaudeCliAdapter
from infrastructure.llm.claude_code_deepseek import DeepSeekClaudeCodeAdapter
from infrastructure.llm.dispatcher import invoke

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _hermetic_llm_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """셸에 set 된 DEEPSEEK_API_KEY / LLM_VENDOR / ANTHROPIC_* 의존 제거 — 테스트 결정성.

    adapter 는 명시 token 이 없으면 .env 의 DEEPSEEK_API_KEY 를 load_env_file 로 읽으므로,
    skip-경로 테스트는 항상 명시 token="" 을 주입한다. 본 fixture 는 ambient env 만 격리.
    """
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("LLM_VENDOR", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("ANTHROPIC_BASE_URL", raising=False)


class TestClaudeCliAdapter:
    """claude-cli adapter — subprocess command 조립 / binary-absent skip / env 상속."""

    def test_command_assembly_dry_run(self) -> None:
        adapter = ClaudeCliAdapter(binary="/fake/claude")
        result = adapter.invoke(
            "/stage4-thesis-auditor 2026-06-05",
            allowed_tools="Bash,Read,Write,Edit,Glob,Grep",
            dry_run=True,
        )
        assert result.status == "dry_run"
        assert result.cmd == [
            "/fake/claude",
            "-p",
            "/stage4-thesis-auditor 2026-06-05",
            "--allowed-tools",
            "Bash,Read,Write,Edit,Glob,Grep",
        ]

    def test_no_allowed_tools_omits_flag(self) -> None:
        adapter = ClaudeCliAdapter(binary="/fake/claude")
        result = adapter.invoke("hello", dry_run=True)
        assert result.cmd == ["/fake/claude", "-p", "hello"]
        assert "--allowed-tools" not in result.cmd

    def test_binary_absent_skips(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "infrastructure.llm.claude_cli.shutil.which", lambda _name: None
        )
        adapter = ClaudeCliAdapter()
        result = adapter.invoke("/skill", dry_run=True)
        assert result.status == "skipped"
        assert result.skip_reason and "claude CLI" in result.skip_reason

    def test_subprocess_env_default_is_none(self) -> None:
        """base adapter 는 부모 env 상속 (None) — 기존 동작 불변."""
        adapter = ClaudeCliAdapter(binary="/fake/claude")
        assert adapter._subprocess_env() is None


class TestDeepSeekClaudeCodeAdapter:
    """claude harness + DeepSeek 백엔드 — env 주입 / Anthropic 차단 / key-absent skip."""

    def test_dry_run_cmd_matches_claude_cli(self) -> None:
        """cmd 조립은 claude-cli 와 동일 — 토큰은 cmd 에 미노출 (env 로만 전달)."""
        adapter = DeepSeekClaudeCodeAdapter(binary="/fake/claude", token="test-key")
        result = adapter.invoke(
            "/stage4-thesis-auditor 2026-06-05",
            allowed_tools="Bash,Read,Write",
            dry_run=True,
        )
        assert result.status == "dry_run"
        assert result.cmd == [
            "/fake/claude",
            "-p",
            "/stage4-thesis-auditor 2026-06-05",
            "--allowed-tools",
            "Bash,Read,Write",
        ]
        assert "test-key" not in " ".join(result.cmd)

    def test_subprocess_env_redirects_to_deepseek(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "should-be-removed")
        adapter = DeepSeekClaudeCodeAdapter(binary="/fake/claude", token="test-key")
        env = adapter._subprocess_env()
        # Anthropic 직결 차단
        assert "ANTHROPIC_API_KEY" not in env
        # DeepSeek 백엔드로 강제 redirect
        assert env["ANTHROPIC_BASE_URL"] == "https://api.deepseek.com/anthropic"
        assert env["ANTHROPIC_AUTH_TOKEN"] == "test-key"
        # 모델/effort 기본값
        assert env["ANTHROPIC_MODEL"] == "deepseek-v4-pro[1m]"
        assert env["ANTHROPIC_DEFAULT_OPUS_MODEL"] == "deepseek-v4-pro[1m]"
        assert env["ANTHROPIC_DEFAULT_SONNET_MODEL"] == "deepseek-v4-pro[1m]"
        assert env["ANTHROPIC_DEFAULT_HAIKU_MODEL"] == "deepseek-v4-flash"
        assert env["CLAUDE_CODE_SUBAGENT_MODEL"] == "deepseek-v4-flash"
        assert env["CLAUDE_CODE_EFFORT_LEVEL"] == "max"

    def test_model_env_override_preserved(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """사용자가 모델 env 를 이미 설정했으면 존중 (setdefault)."""
        monkeypatch.setenv("ANTHROPIC_MODEL", "deepseek-custom")
        adapter = DeepSeekClaudeCodeAdapter(binary="/fake/claude", token="test-key")
        env = adapter._subprocess_env()
        assert env["ANTHROPIC_MODEL"] == "deepseek-custom"
        # 단 base_url / auth_token 은 강제
        assert env["ANTHROPIC_BASE_URL"] == "https://api.deepseek.com/anthropic"

    def test_key_absent_skips(self) -> None:
        """DEEPSEEK_API_KEY 부재 → skipped (실행 모드에서도 API 호출 방지)."""
        adapter = DeepSeekClaudeCodeAdapter(binary="/fake/claude", token="")
        result = adapter.invoke("/skill", dry_run=False)
        assert result.status == "skipped"
        assert result.skip_reason and "DEEPSEEK_API_KEY" in result.skip_reason


class TestDispatcher:
    """dispatcher.invoke() — vendor resolution, REGISTRY, error paths."""

    def test_invoke_defaults_to_claude_cli_deepseek(self) -> None:
        """기본 vendor 가 claude-cli-deepseek 인지 확인 (dry-run — subprocess 없음)."""
        result = invoke("/skill", dry_run=True)
        assert result.vendor == "claude-cli-deepseek"

    def test_invoke_unknown_vendor_errors(self) -> None:
        result = invoke("/skill", vendor="nonexistent-vendor", dry_run=True)
        assert result.status == "error"
        assert "unknown LLM vendor" in (result.error or "")

    def test_vendor_env_override_claude_cli(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """claude-cli (순수 Anthropic) 로 rollback override 가능."""
        monkeypatch.setenv("LLM_VENDOR", "claude-cli")
        result = invoke("/skill", dry_run=True)
        assert result.vendor == "claude-cli"

    def test_vendor_env_override_claude_cli_deepseek(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("LLM_VENDOR", "claude-cli-deepseek")
        result = invoke("/skill", dry_run=True)
        assert result.vendor == "claude-cli-deepseek"

    def test_registry_vendors(self) -> None:
        assert "claude-cli" in REGISTRY
        assert "claude-cli-deepseek" in REGISTRY
        assert "deepseek" not in REGISTRY  # single-turn vendor 회수 (ADR-0016)
        assert REGISTRY["claude-cli"] is ClaudeCliAdapter
        assert REGISTRY["claude-cli-deepseek"] is DeepSeekClaudeCodeAdapter
