"""
.claude/hooks/_inject_directive_context.py — UserPromptSubmit body.

inject_directive_context.sh 가 호출. INVEST_HOOK_INPUT (JSON) 을 읽어 prompt 를
분석하고, 매칭된 coding directive 본문을 hookSpecificOutput.additionalContext
로 출력. 매칭 없으면 빈 객체 {}.

매칭 매트릭스:
    - 항상 inject (코드 작업 keyword 매치 시): 00-principles.md
    - 추가 매칭:
        .py    → 10-python.md
        .sh    → 11-shell.md
        .yaml / .json / .env / .md → 12-config-text.md
        모든 코드 작업 → 20-quality.md + 30-security.md
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from _directive_lint import (  # type: ignore  # noqa: E402
    audit_log,
    load_directive_bodies,
    resolve_invest_root,
)

HOOK_NAME = "inject_directive_context"

RAW = os.environ.get("INVEST_HOOK_INPUT", "")
try:
    payload = json.loads(RAW) if RAW.strip() else {}
except Exception:
    payload = {}

prompt = (payload.get("prompt") or "").strip()

# ---------------------------------------------------------------------------
# 트리거 매칭
# ---------------------------------------------------------------------------
CODE_KEYWORDS = [
    # 한국어
    "코드", "구현", "작성", "추가", "수정", "함수", "모듈", "테스트",
    "리팩터", "리팩토링", "리뷰",
    # 영어
    "code", "implement", "write", "edit", "modify", "fix", "refactor",
    "function", "module", "class", "test", "review",
    # tool 명
    "Write", "Edit", "Bash",
]

EXT_TO_FILES: dict[str, list[str]] = {
    ".py":   ["10-python.md", "20-quality.md", "30-security.md"],
    ".sh":   ["11-shell.md",  "20-quality.md", "30-security.md"],
    ".yaml": ["12-config-text.md", "30-security.md"],
    ".yml":  ["12-config-text.md", "30-security.md"],
    ".json": ["12-config-text.md"],
    ".env":  ["12-config-text.md", "30-security.md"],
    ".md":   ["12-config-text.md"],
}

# prompt 에서 파일 경로(또는 확장자) 패턴 추출
_FILE_HINT_RE = re.compile(r"[\w./_-]+\.(py|sh|ya?ml|json|env|md)\b")

prompt_lower = prompt.lower()
keyword_hit = any(kw.lower() in prompt_lower for kw in CODE_KEYWORDS)

ext_hits: set[str] = set()
for m in _FILE_HINT_RE.finditer(prompt):
    ext = "." + m.group(1).lower().replace("yml", "yaml")
    ext_hits.add(ext)

# trigger 결정
should_inject = keyword_hit or bool(ext_hits)

if not should_inject:
    audit_log(HOOK_NAME, "SKIP", "no_code_keyword_no_ext_hint")
    print("{}")
    sys.exit(0)


# ---------------------------------------------------------------------------
# Build inject payload
# ---------------------------------------------------------------------------
try:
    root = resolve_invest_root()
except SystemExit:
    audit_log(HOOK_NAME, "SKIP", "invest_root_unresolved")
    print("{}")
    sys.exit(0)

bodies = load_directive_bodies(root)
if not bodies:
    audit_log(HOOK_NAME, "SKIP", "directives_dir_empty")
    print("{}")
    sys.exit(0)

# 항상 00-principles.md 포함
files_to_inject: list[str] = ["00-principles.md"]

# extension hit 별로 매핑된 파일 추가 (중복 제거)
for ext in ext_hits:
    for fname in EXT_TO_FILES.get(ext, []):
        if fname not in files_to_inject:
            files_to_inject.append(fname)

# extension hit 가 없으면 코드 키워드만 있는 경우 — 보수적으로 python+quality+security
if not ext_hits and keyword_hit:
    for fname in ("10-python.md", "20-quality.md", "30-security.md"):
        if fname not in files_to_inject:
            files_to_inject.append(fname)

# AGENTS.md (directive 인덱스, 구 README.md) 는 첫 줄만 매칭 안내용으로 prepend
readme_text = ""
for rel, text in bodies.items():
    if rel.endswith("/AGENTS.md"):
        readme_text = text
        break

# bodies 의 key 는 repo-relative path (e.g. governance/directives/10-python.md).
# fname (e.g. "10-python.md") 와 매칭하려면 basename 비교.
basename_to_body: dict[str, str] = {}
for rel, text in bodies.items():
    basename_to_body[rel.rsplit("/", 1)[-1]] = text

selected_bodies: list[str] = []
for fname in files_to_inject:
    body = basename_to_body.get(fname)
    if body:
        selected_bodies.append(body.strip())

if not selected_bodies:
    audit_log(HOOK_NAME, "SKIP", f"no_matching_body files={files_to_inject}")
    print("{}")
    sys.exit(0)

header = (
    "# [auto-injected] Coding Directives\n"
    "본 텍스트는 .claude/hooks/inject_directive_context.sh 가 UserPromptSubmit\n"
    "시점에 자동 주입한 코딩 컨벤션입니다. 본문 위반은 PreToolUse / PostToolUse\n"
    "hook (block_anti_patterns / lint_directives) 이 stderr 에 D-ID 인용으로\n"
    "차단/경고합니다. 작업 전 본문 D-XX-N ID 를 참고해 작성하세요.\n\n"
    f"매칭된 directive 파일: {', '.join(files_to_inject)}\n"
)

inject = header + "\n\n---\n\n" + "\n\n---\n\n".join(selected_bodies)

audit_log(HOOK_NAME, "INJECT", f"files={','.join(files_to_inject)} bytes={len(inject)}")

out = {
    "hookSpecificOutput": {
        "hookEventName": "UserPromptSubmit",
        "additionalContext": inject,
    }
}
print(json.dumps(out, ensure_ascii=False))
