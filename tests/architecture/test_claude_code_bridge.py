"""
불변식 — Claude Code skill-discovery 브릿지 (ADR-0016).

`claude` CLI(=production LLM harness, DeepSeek 백엔드)는 `CLAUDE.md` 프로젝트 메모리와
`.claude/skills/` 스킬 경로만 인식한다. 본 저장소의 SSoT 는 `AGENTS.md` + `.agents/skills/`
(Zed/Kiro 컨벤션) 이므로, 두 심볼릭이 SSoT 로 정확히 resolve 함을 고정한다.

- `CLAUDE.md`        → `AGENTS.md`
- `.claude/skills`   → `.agents/skills`

심볼릭은 git 커밋된 인프라(claude CLI 의존성). `.claude/commands/` 는 의도적으로 만들지
않는다 — headless 호출은 슬래시/Agent SDK 대신 explicit-path 지시문 프롬프트로 수행한다
(run_daily_local.sh). 따라서 본 테스트는 commands parity 를 검사하지 않는다.
"""

from __future__ import annotations

import pathlib

import pytest

# tests/architecture/test_claude_code_bridge.py → parents[2] = repo root
REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


@pytest.mark.arch
def test_claude_md_symlinks_to_agents_md() -> None:
    """`CLAUDE.md` 는 `AGENTS.md` 로 resolve 하는 심볼릭이어야 한다 (Claude Code 메모리 브릿지)."""
    claude_md = REPO_ROOT / "CLAUDE.md"
    agents_md = REPO_ROOT / "AGENTS.md"
    assert claude_md.is_symlink(), "CLAUDE.md 가 심볼릭이 아님 (AGENTS.md 브릿지 필요)"
    assert claude_md.resolve() == agents_md.resolve(), (
        f"CLAUDE.md 가 AGENTS.md 로 resolve 하지 않음: {claude_md.resolve()}"
    )


@pytest.mark.arch
def test_claude_skills_symlinks_to_agents_skills() -> None:
    """`.claude/skills` 는 `.agents/skills` 로 resolve 하는 심볼릭이어야 한다 (Claude Code 스킬 브릿지)."""
    claude_skills = REPO_ROOT / ".claude" / "skills"
    agents_skills = REPO_ROOT / ".agents" / "skills"
    assert claude_skills.is_symlink(), ".claude/skills 가 심볼릭이 아님 (.agents/skills 브릿지 필요)"
    assert claude_skills.resolve() == agents_skills.resolve(), (
        f".claude/skills 가 .agents/skills 로 resolve 하지 않음: {claude_skills.resolve()}"
    )


@pytest.mark.arch
def test_pipeline_skills_reachable_via_bridge() -> None:
    """headless dispatch 대상 스킬(stage4/stage6)이 .claude/skills 브릿지로 도달 가능해야 한다."""
    for skill in ("stage4-thesis-auditor", "stage6-brief-author"):
        skill_md = REPO_ROOT / ".claude" / "skills" / skill / "SKILL.md"
        assert skill_md.is_file(), f".claude/skills/{skill}/SKILL.md 도달 불가 (브릿지 깨짐)"
