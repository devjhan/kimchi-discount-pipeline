"""
.claude/hooks/_lint_directives.py — PostToolUse directive lint (dry-run M1).

lint_directives.sh 가 호출. Write/Edit 직후 file_path 를 read 해 directive
위반을 audit log 에 기록 (M1=dry-run). M2 부터는 mode=warn/enforce 로 inject
또는 block.

검사 항목 (M1):
    - D-PY-2  public 함수 서명 타입 힌트 (ast.parse)
    - D-PY-3  except Exception 무 noqa
    - D-PY-5  public 함수 docstring 부재
    - D-CFG-2 $TRAIL_TODAY/*.json envelope 5 필드
    - D-CFG-3 yaml 들여쓰기 (탭 / 4 칸 검사)

M1 은 dry-run — finding 발견해도 exit 0 + audit log 만.
"""

from __future__ import annotations

import ast
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from _directive_lint import (  # type: ignore  # noqa: E402
    audit_log,
    is_governance_yaml,
    is_python_source,
    is_trail_json,
)

HOOK_NAME = "lint_directives"
MODE = os.environ.get("INVEST_DIRECTIVE_LINT_MODE", "dry-run").lower()

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

# Self / directive 본문 skip
_self_paths = (
    "governance/directives/",
    ".claude/hooks/_directive_lint.py",
    ".claude/hooks/_block_anti_patterns.py",
    ".claude/hooks/_inject_directive_context.py",
    ".claude/hooks/_lint_directives.py",
)
if any(s in file_path for s in _self_paths):
    sys.exit(0)


# ---------------------------------------------------------------------------
# Helpers — read 파일 (Write 직후이므로 disk 에 있음)
# ---------------------------------------------------------------------------
def read_file() -> str | None:
    try:
        return Path(file_path).read_text(encoding="utf-8")
    except Exception:
        return None


# ---------------------------------------------------------------------------
# D-PY checks (ast based)
# ---------------------------------------------------------------------------
def lint_python(text: str) -> list[tuple[str, str]]:
    """ast.parse 기반 D-PY-2 / D-PY-3 / D-PY-5 검사. return [(d_id, detail), ...]."""
    out: list[tuple[str, str]] = []
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        out.append(("D-PY-syntax", f"SyntaxError L{exc.lineno}: {exc.msg}"))
        return out

    source_lines = text.splitlines()

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            name = node.name
            is_public = not name.startswith("_")
            if is_public:
                # D-PY-2: 모든 args + return 에 annotation
                args_missing = [a.arg for a in node.args.args if a.annotation is None and a.arg != "self"]
                if args_missing:
                    out.append((
                        "D-PY-2",
                        f"L{node.lineno} func {name!r}: args without typing: {args_missing}",
                    ))
                if node.returns is None:
                    out.append((
                        "D-PY-2",
                        f"L{node.lineno} func {name!r}: missing return type annotation",
                    ))
                # D-PY-5: docstring 부재
                if not (
                    node.body
                    and isinstance(node.body[0], ast.Expr)
                    and isinstance(node.body[0].value, ast.Constant)
                    and isinstance(node.body[0].value.value, str)
                ):
                    out.append((
                        "D-PY-5",
                        f"L{node.lineno} func {name!r}: missing docstring",
                    ))
        if isinstance(node, ast.ExceptHandler):
            if (
                isinstance(node.type, ast.Name)
                and node.type.id == "Exception"
            ):
                # D-PY-3: 같은 줄 또는 직전 줄 # noqa: BLE001 코멘트 검사
                ln = node.lineno - 1  # 0-indexed
                if 0 <= ln < len(source_lines):
                    line_text = source_lines[ln]
                    has_noqa = "noqa: BLE001" in line_text or "noqa:BLE001" in line_text
                    if not has_noqa:
                        out.append((
                            "D-PY-3",
                            f"L{node.lineno} bare `except Exception` without `# noqa: BLE001`",
                        ))
    return out


# ---------------------------------------------------------------------------
# D-CFG-2: trail JSON envelope
# ---------------------------------------------------------------------------
ENVELOPE_FIELDS = ("schema", "generated_at", "date", "config_version", "warnings")


def lint_trail_json(text: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    try:
        obj = json.loads(text)
    except json.JSONDecodeError as exc:
        out.append(("D-CFG-2", f"invalid JSON: {exc.msg}"))
        return out
    if not isinstance(obj, dict):
        out.append(("D-CFG-2", "root is not object — envelope cannot be checked"))
        return out
    missing = [f for f in ENVELOPE_FIELDS if f not in obj]
    if missing:
        out.append(("D-CFG-2", f"missing envelope fields: {missing}"))
    return out


# ---------------------------------------------------------------------------
# D-CFG-3: governance yaml indent (탭 / 4 칸 검사)
# ---------------------------------------------------------------------------
_TAB_INDENT_RE = re.compile(r"^\t+\S")
_FOUR_SPACE_INDENT_RE = re.compile(r"^    \S")  # 4 space indent (탭 변환 제외)


def lint_yaml_indent(text: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    tab_lines: list[int] = []
    four_lines: list[int] = []
    for ln, line in enumerate(text.splitlines(), 1):
        if _TAB_INDENT_RE.match(line):
            tab_lines.append(ln)
        elif _FOUR_SPACE_INDENT_RE.match(line):
            four_lines.append(ln)
    if tab_lines:
        out.append(("D-CFG-3", f"tab indentation at lines {tab_lines[:5]}"))
    if four_lines:
        out.append(("D-CFG-3", f"4-space indentation at lines {four_lines[:5]} (expected 2)"))
    return out


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------
findings: list[tuple[str, str]] = []

content = read_file()
if content is None:
    audit_log(HOOK_NAME, "SKIP", f"read_failed file={file_path}")
    sys.exit(0)

if is_python_source(file_path):
    findings.extend(lint_python(content))
elif is_trail_json(file_path):
    findings.extend(lint_trail_json(content))
elif is_governance_yaml(file_path):
    findings.extend(lint_yaml_indent(content))

# ---------------------------------------------------------------------------
# Decision (mode-dispatch)
# ---------------------------------------------------------------------------
if not findings:
    audit_log(HOOK_NAME, "ALLOW", f"clean mode={MODE} file={file_path}")
    sys.exit(0)

# build human reason
SHOWN = findings[:20]
extra = len(findings) - len(SHOWN)
reason_lines = [
    f"[lint-directives] {len(findings)} finding(s) in {file_path}.",
    "각 finding 의 D-ID 본문은 $DIRECTIVES_DIR 아래 해당 파일에 정의됨.",
]
for d_id, detail in SHOWN:
    reason_lines.append(f"  - {d_id}: {detail}")
if extra > 0:
    reason_lines.append(f"  ... +{extra} more")
reason = "\n".join(reason_lines)

audit_decision_label = f"DRY_RUN_FOUND" if MODE == "dry-run" else "WARN" if MODE == "warn" else "BLOCK"
audit_log(
    HOOK_NAME,
    audit_decision_label,
    f"mode={MODE} file={file_path} findings={len(findings)}",
)

if MODE == "dry-run":
    # M1: audit log 만, exit 0 — 사용자/에이전트에 출력 안 함
    sys.exit(0)

if MODE == "warn":
    out = {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": reason,
        }
    }
    print(json.dumps(out, ensure_ascii=False))
    sys.exit(0)

# enforce (M2)
out = {
    "hookSpecificOutput": {
        "hookEventName": "PostToolUse",
        "additionalContext": reason,
    },
    "decision": "block",
    "reason": reason,
}
print(json.dumps(out, ensure_ascii=False))
sys.exit(0)
