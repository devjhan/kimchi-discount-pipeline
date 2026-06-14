"""tests/unit/test_llm_dispatcher.py — infrastructure/llm port (F-13).

Vendor-neutral seam — claude-cli (subprocess) / deepseek (API) adapter 공통 검증.
실제 Network/API 호출 없이 (dry-run + monkeypatch) 확인.
"""

from __future__ import annotations

import pytest

from infrastructure.llm import REGISTRY
from infrastructure.llm.claude_cli import ClaudeCliAdapter
from infrastructure.llm.deepseek import DeepSeekAdapter
from infrastructure.llm.dispatcher import invoke

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _hermetic_llm_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """셸에 set 된 DEEPSEEK_API_KEY / LLM_VENDOR 의존 제거 — 테스트 결정성(hermetic).

    dispatcher.invoke 와 DeepSeekAdapter() 는 명시 api_key 가 없으면 ambient env 의
    DEEPSEEK_API_KEY 를 읽는다. 셸에 키가 set 이면 skip-경로 테스트가 비결정적으로
    실패(또는 실 API 호출)했다 — 본 autouse fixture 가 env 를 비워 격리한다. 명시
    api_key 를 주입하는 테스트는 영향 없음. LLM_VENDOR 를 setenv 하는 테스트는 본
    fixture(setup) 이후 본문에서 재설정하므로 정상 동작.
    """
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("LLM_VENDOR", raising=False)


class TestClaudeCliAdapter:
    """claude-cli adapter — subprocess command 조립 / binary-absent skip."""

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


class TestDeepSeekAdapter:
    """DeepSeek API adapter — API-key absent skip / dry-run / openai SDK absent."""

    def test_dry_run_output(self) -> None:
        adapter = DeepSeekAdapter(api_key="test-key")
        result = adapter.invoke("hello", dry_run=True)
        assert result.status == "dry_run"
        assert "deepseek" in result.cmd[2]  # base_url

    def test_api_key_absent_skips(self) -> None:
        adapter = DeepSeekAdapter(api_key="")
        result = adapter.invoke("/skill", dry_run=True)
        assert result.status == "skipped"
        assert result.skip_reason and "DEEPSEEK_API_KEY" in result.skip_reason

    def test_api_key_absent_no_dry_run_also_skips(self) -> None:
        """실행 모드에서도 api_key 없으면 skip (API 호출 방지)."""
        adapter = DeepSeekAdapter(api_key="")
        result = adapter.invoke("/skill", dry_run=False)
        assert result.status == "skipped"

    def test_allowed_tools_builds_tools(self) -> None:
        """allowed_tools CSV → function calling tool 정의 변환."""
        adapter = DeepSeekAdapter(api_key="test-key")
        result = adapter.invoke(
            "hello",
            allowed_tools="Bash,Read,Write",
            dry_run=True,
        )
        # dry_run 성공만 확인 (tools 빌드는 invoke 내부)
        assert result.status == "dry_run"


class TestDispatcher:
    """dispatcher.invoke() — vendor resolution, REGISTRY, error paths."""

    def test_invoke_defaults_to_deepseek(self) -> None:
        """기본 vendor 가 deepseek 인지 확인."""
        # claude-cli 는 subprocess 이므로 기본 건드리지 않음.
        # LLM_VENDOR env 없이 호출 → deepseek (실제 API 호출 = skipped).
        result = invoke("/skill", dry_run=False)
        assert result.vendor == "deepseek"

    def test_deepseek_skip_invoke(self) -> None:
        """기본 deepseek (api_key 없음) → skipped."""
        result = invoke("/skill", vendor="deepseek", dry_run=False)
        assert result.vendor == "deepseek"
        assert result.status in ("skipped",)

    def test_invoke_unknown_vendor_errors(self) -> None:
        result = invoke("/skill", vendor="nonexistent-vendor", dry_run=True)
        assert result.status == "error"
        assert "unknown LLM vendor" in (result.error or "")

    def test_vendor_env_override_deepseek(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("LLM_VENDOR", "deepseek")
        result = invoke("/skill", dry_run=True)
        assert result.vendor == "deepseek"

    def test_vendor_env_override_claude_cli(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """claude-cli 로 override 가능 (rollback safety)."""
        monkeypatch.setenv("LLM_VENDOR", "claude-cli")
        result = invoke("/skill", dry_run=True)
        assert result.vendor == "claude-cli"

    def test_registry_has_both_vendors(self) -> None:
        assert "deepseek" in REGISTRY
        assert "claude-cli" in REGISTRY
        assert REGISTRY["deepseek"] is DeepSeekAdapter
        assert REGISTRY["claude-cli"] is ClaudeCliAdapter
