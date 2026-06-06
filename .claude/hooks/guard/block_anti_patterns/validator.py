"""
.claude/hooks/_block_anti_patterns.py — PreToolUse anti-pattern guard.

block_anti_patterns.sh 가 호출. INVEST_HOOK_INPUT 의 tool_input 에서 작성하려는
content + file_path 를 읽고, D-PY-1 / D-SH-1 / D-CFG-1 / D-SEC-1 anti-pattern
검출 시 exit 2 + stderr 출력 + audit log.

출력 형식 (D-SH-3 표준):
    [block-anti-patterns] {N} violation(s) in {file}.
    {D-ID} 위반: {짧은 설명}
      - Fix: {1줄 가이드}
    참조: $DIRECTIVES_DIR/{file}#{anchor}

우회:
    INVEST_DIRECTIVE_GUARD_OFF=1   전역 off
    INVEST_SEC_GUARD_OFF=1         D-SEC-1 secret 검사만 off
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from _directive_lint import (  # type: ignore  # noqa: E402
    audit_log,
    detect_py_missing_future,
    detect_secret_like,
    detect_sh_missing_set,
    detect_yaml_missing_header,
    is_governance_yaml,
    is_python_source,
    is_shell_hook,
)

HOOK_NAME = "block_anti_patterns"

# ---------------------------------------------------------------------------
# Global off-switch
# ---------------------------------------------------------------------------
if os.environ.get("INVEST_DIRECTIVE_GUARD_OFF") == "1":
    audit_log(HOOK_NAME, "BYPASS", "INVEST_DIRECTIVE_GUARD_OFF=1")
    sys.exit(0)

RAW = os.environ.get("INVEST_HOOK_INPUT", "")
try:
    payload = json.loads(RAW) if RAW.strip() else {}
except Exception:
    audit_log(HOOK_NAME, "SKIP", "invalid_json")
    sys.exit(0)

tool_name = payload.get("tool_name") or ""
tool_input = payload.get("tool_input") or {}

if tool_name not in {"Write", "Edit"}:
    sys.exit(0)

file_path: str = tool_input.get("file_path") or ""
if not file_path:
    sys.exit(0)

# Write: content. Edit: new_string.
content: str = tool_input.get("content") or tool_input.get("new_string") or ""
if not content.strip():
    sys.exit(0)


# ---------------------------------------------------------------------------
# Violation collection
# ---------------------------------------------------------------------------
violations: list[tuple[str, str, str]] = []   # (d_id, summary, fix)

# Skip self — directive 본문 자체나 hook 자체는 검사 대상 외
# (legacy-ok fence 안 anti-pattern 데모 코드는 의도적)
_self_paths = (
    "governance/directives/",
    ".claude/hooks/_directive_lint.py",
    ".claude/hooks/_block_anti_patterns.py",
    ".claude/hooks/_inject_directive_context.py",
    ".claude/hooks/_lint_directives.py",
)
if any(s in file_path for s in _self_paths):
    audit_log(HOOK_NAME, "SKIP", f"self_path file={file_path}")
    sys.exit(0)

# D-PY-1: from __future__ import annotations
if is_python_source(file_path) and tool_name == "Write":
    if detect_py_missing_future(content):
        violations.append((
            "D-PY-1",
            f"{file_path} 헤더 30 줄 내 `from __future__ import annotations` 부재",
            "파일 최상단 (module docstring 직후) 에 한 줄 추가",
        ))

# D-SH-1: set -uo pipefail
if is_shell_hook(file_path) and tool_name == "Write":
    if detect_sh_missing_set(content):
        violations.append((
            "D-SH-1",
            f"{file_path} 헤더 10 줄 내 `set -uo pipefail` 부재",
            "shebang 직후 (또는 module 주석 직후) `set -uo pipefail` 추가",
        ))

# D-CFG-1: governance/*.yaml version + description
if is_governance_yaml(file_path) and tool_name == "Write":
    missing_v, missing_d = detect_yaml_missing_header(content)
    if missing_v or missing_d:
        miss_str = " + ".join(
            x for x, present in (("version:", not missing_v), ("description:", not missing_d))
            if not present
        )
        violations.append((
            "D-CFG-1",
            f"{file_path} 헤더 10 줄 내 {miss_str} 부재",
            "파일 첫 줄에 `version: \"1.0\"` + 둘째 줄에 `description: \"...\"` 추가",
        ))

# D-SEC-1: secret-like literal
if os.environ.get("INVEST_SEC_GUARD_OFF") != "1":
    hits = detect_secret_like(content)
    if hits:
        types = ",".join(sorted(set(t for t, _ in hits)))
        violations.append((
            "D-SEC-1",
            f"{file_path} 본문에 secret-like 패턴 {len(hits)} 건 (types={types})",
            "literal 제거 + os.environ.get('VAR_NAME') 경유로 $ENV_PATH 에서 read",
        ))

# ---------------------------------------------------------------------------
# Decision
# ---------------------------------------------------------------------------
if not violations:
    audit_log(HOOK_NAME, "ALLOW", f"clean file={file_path}")
    sys.exit(0)

# stderr 출력 (D-SH-3 형식)
print(f"[block-anti-patterns] {len(violations)} violation(s) in {file_path}.", file=sys.stderr)
for d_id, summary, fix in violations:
    print(f"  {d_id}: {summary}", file=sys.stderr)
    print(f"    Fix: {fix}", file=sys.stderr)
print(
    "참조: $DIRECTIVES_DIR/AGENTS.md (D-ID 표). "
    "false positive 시: INVEST_DIRECTIVE_GUARD_OFF=1 (전역) / "
    "INVEST_SEC_GUARD_OFF=1 (D-SEC-1 만)",
    file=sys.stderr,
)

audit_log(
    HOOK_NAME,
    "BLOCK",
    f"file={file_path} violations={','.join(v[0] for v in violations)}",
)
sys.exit(2)
