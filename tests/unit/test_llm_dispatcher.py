"""tests/unit/test_llm_dispatcher.py — infrastructure/llm port (F-13).

claude -p 호출의 vendor-neutral seam — command 조립 / dry-run / binary-absent skip /
unknown vendor 검증. 실제 claude 실행 없이 (fake binary + monkeypatch) 확인.
"""
from __future__ import annotations

import pytest

from infrastructure.llm import REGISTRY
from infrastructure.llm.adapter import LlmResult
from infrastructure.llm.claude_cli import ClaudeCliAdapter
from infrastructure.llm.dispatcher import invoke

pytestmark = pytest.mark.unit


class TestClaudeCliAdapter:
    def test_command_assembly_dry_run(self) -> None:
        adapter = ClaudeCliAdapter(binary="/fake/claude")
        result = adapter.invoke(
            "/investment-stage4-thesis-auditor 2026-06-05",
            allowed_tools="Bash,Read,Write,Edit,Glob,Grep",
            dry_run=True,
        )
        assert result.status == "dry_run"
        assert result.cmd == [
            "/fake/claude",
            "-p",
            "/investment-stage4-thesis-auditor 2026-06-05",
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


class TestDispatcher:
    def test_invoke_defaults_to_claude_cli(self) -> None:
        result = invoke("/skill", allowed_tools="Read", dry_run=True)
        assert isinstance(result, LlmResult)
        assert result.vendor == "claude-cli"
        assert result.status in ("dry_run", "skipped")  # claude 존재 여부 무관

    def test_unknown_vendor_errors(self) -> None:
        result = invoke("/skill", vendor="nonexistent-vendor", dry_run=True)
        assert result.status == "error"
        assert "unknown LLM vendor" in (result.error or "")

    def test_vendor_env_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LLM_VENDOR", "claude-cli")
        result = invoke("/skill", dry_run=True)
        assert result.vendor == "claude-cli"

    def test_registry_has_claude_cli(self) -> None:
        assert "claude-cli" in REGISTRY
        assert REGISTRY["claude-cli"] is ClaudeCliAdapter
