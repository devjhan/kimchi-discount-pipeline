"""inject_guidelines — UserPromptSubmit hook 본체.

prompt 에서 file / dir path 후보 추출 → 각 path 의 부모 디렉토리 chain walk →
발견된 모든 ``.guidelines/*.md`` 본문을 hookSpecificOutput.additionalContext
로 inject. 매칭 없으면 빈 객체 ``{}`` (zero overhead).

도메인 로컬 컨벤션 — ``domains/screener/.guidelines/`` 등 패키지별 .guidelines
디렉토리가 본 hook 의 자동 주입 대상. 새 도메인이 .guidelines 디렉토리를
추가하면 zero-config 자동 인식.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from _directive_lint import audit_log, resolve_invest_root  # type: ignore  # noqa: E402

HOOK_NAME = "inject_guidelines"

RAW = os.environ.get("INVEST_HOOK_INPUT", "")
try:
    payload = json.loads(RAW) if RAW.strip() else {}
except (json.JSONDecodeError, TypeError):
    payload = {}

prompt = (payload.get("prompt") or "").strip()

# path-like token — slash 가 1+ 등장하고 영숫자/_/-/./ 만 포함.
# 자연어의 일반 단어가 아닌 file/dir path 만 캡처하기 위함.
_PATH_RE = re.compile(r"(?<![A-Za-z0-9])([A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)+)")

invest_root = resolve_invest_root()

# ---------------------------------------------------------------------------
# path 후보 수집
# ---------------------------------------------------------------------------
candidates: set[Path] = set()
for m in _PATH_RE.finditer(prompt):
    raw = m.group(1).rstrip("/.")
    if not raw:
        continue
    p_raw = Path(raw)
    p = p_raw.resolve() if p_raw.is_absolute() else (invest_root / raw).resolve()
    # invest_root 외부는 무시 — 다른 프로젝트 / system path 우발 매칭 방지
    try:
        p.relative_to(invest_root)
    except ValueError:
        continue
    candidates.add(p)

# ---------------------------------------------------------------------------
# 부모 walk → .guidelines 디렉토리 발견
# ---------------------------------------------------------------------------
found_dirs: set[Path] = set()
for p in candidates:
    # 파일이면 부모부터, 디렉토리면 자체부터. 존재 여부는 무관 (prompt 상 미래 path).
    start = p if (p.exists() and p.is_dir()) else p.parent
    for parent in [start, *start.parents]:
        try:
            parent.relative_to(invest_root)
        except ValueError:
            break
        gdir = parent / ".guidelines"
        if gdir.is_dir():
            found_dirs.add(gdir)

if not found_dirs:
    sys.stdout.write(json.dumps({}))
    audit_log(HOOK_NAME, "SKIP", "no_guidelines_match")
    sys.exit(0)

# ---------------------------------------------------------------------------
# 본문 수집 + inject
# ---------------------------------------------------------------------------
sections: list[str] = []
for gdir in sorted(found_dirs):
    try:
        rel_dir = gdir.relative_to(invest_root)
    except ValueError:
        rel_dir = gdir
    for md in sorted(gdir.glob("*.md")):
        try:
            body = md.read_text(encoding="utf-8")
        except OSError:
            continue
        sections.append(f"### {rel_dir}/{md.name}\n\n{body}")

content = (
    "# [auto-injected] Local Guidelines\n"
    "본 텍스트는 .claude/hooks/context/inject_guidelines/ 가 prompt 에 등장한 "
    "file/dir path 의 상위 디렉토리를 walk 해 자동 주입한 도메인 로컬 컨벤션입니다.\n"
    "전역 코딩 directive (governance/directives/) 와 별개로, 패키지별 특화 룰을 "
    "지역적으로 강제합니다.\n\n"
    + "\n\n---\n\n".join(sections)
)

out = {
    "hookSpecificOutput": {
        "hookEventName": "UserPromptSubmit",
        "additionalContext": content,
    }
}
sys.stdout.write(json.dumps(out, ensure_ascii=False))
audit_log(HOOK_NAME, "INJECT", f"dirs={len(found_dirs)}")
sys.exit(0)
