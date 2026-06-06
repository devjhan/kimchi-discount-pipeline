"""
.claude/hooks/_directive_lint.py — Coding Directives shared library.

본 모듈은 governance/directives/ 디렉토리의 D-ID 본문을 parse 하고,
세 hook (`_block_anti_patterns.py`, `_inject_directive_context.py`,
`_lint_directives.py`) 이 공통으로 쓰는 helper 를 제공한다.

제공 기능:
    - load_directive_index()        : AGENTS.md (구 README.md) 인덱스 제외, 나머지 directive 파일 D-ID parse
    - load_directive_bodies()       : 각 directive 파일 본문 (D-ID 별로 split)
    - audit_log(name, decision, reason): $AUDIT_DIR/_hook_audit.log append 표준
    - resolve_invest_root()         : INVEST_ROOT 해소 (env / git / fallback)

D-ID 본문 구조 (parse 대상):
    ## D-PY-1 — 모든 .py 헤더에 ...
    **근거**: ...
    ❌ 금지
    ```python
    ...
    ```
    ✅ 올바름
    ...
    **Hook**: ...
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

KST = timezone(timedelta(hours=9))

_D_HEADER_RE = re.compile(r"^##\s+(D-[A-Z]+-\d+)\s*(?:—|--|-)\s*(.+)$", re.MULTILINE)


@dataclass(frozen=True)
class DirectiveEntry:
    d_id: str               # e.g. "D-PY-1"
    title: str              # 한 줄 요약
    file_rel: str           # repo-relative path
    body: str               # 본문 (다음 ## 직전까지)
    hook_hint: str = ""     # 본문 끝 "**Hook**:" 라인 (있을 때)


@dataclass
class DirectiveIndex:
    entries: dict[str, DirectiveEntry] = field(default_factory=dict)
    by_file: dict[str, list[DirectiveEntry]] = field(default_factory=dict)

    def all_ids(self) -> set[str]:
        return set(self.entries.keys())

    def for_file(self, file_rel: str) -> list[DirectiveEntry]:
        return self.by_file.get(file_rel, [])


def resolve_invest_root() -> Path:
    """INVEST_ROOT env / git toplevel / hook 위치 기반 fallback."""
    env_root = os.environ.get("INVEST_ROOT")
    if env_root:
        p = Path(env_root)
        if p.exists():
            return p.resolve()
    # hook 파일 자체 위치 기준 fallback (.claude/hooks/_directive_lint.py)
    here = Path(__file__).resolve()
    candidate = here.parent.parent.parent  # repo root
    if (candidate / ".git").exists() or (candidate / "governance").is_dir():
        return candidate
    raise SystemExit("[directive-lint] cannot resolve INVEST_ROOT")


def directives_dir(root: Path) -> Path:
    """$DIRECTIVES_DIR 해소. env 우선, fallback 으로 root/governance/directives."""
    env_d = os.environ.get("DIRECTIVES_DIR")
    if env_d:
        p = Path(env_d)
        if p.exists():
            return p
    return root / "governance" / "directives"


def _hook_hint(body: str) -> str:
    """본문에서 마지막 **Hook**: 라인 추출 (없으면 빈 문자열)."""
    m = re.search(r"^\*\*Hook\*\*:\s*(.+)$", body, re.MULTILINE)
    return m.group(1).strip() if m else ""


def load_directive_index(root: Path | None = None) -> DirectiveIndex:
    """모든 directive 파일을 walk 해 D-ID entry 수집."""
    root = root or resolve_invest_root()
    ddir = directives_dir(root)
    idx = DirectiveIndex()
    if not ddir.exists():
        return idx
    for md in sorted(ddir.glob("*.md")):
        # AGENTS.md = directive index (구 README.md), CLAUDE.md = 그 symlink. 둘 다 directive 파일 아님.
        if md.name in {"README.md", "AGENTS.md", "CLAUDE.md"}:
            continue
        rel = md.relative_to(root).as_posix()
        text = md.read_text(encoding="utf-8")
        # ## D-XX-N — title 위치 찾고, 다음 ## 직전까지 본문 split
        positions: list[tuple[int, str, str]] = []
        for m in _D_HEADER_RE.finditer(text):
            positions.append((m.start(), m.group(1), m.group(2).strip()))
        # 본문 슬라이스
        file_entries: list[DirectiveEntry] = []
        for i, (start, d_id, title) in enumerate(positions):
            end = positions[i + 1][0] if i + 1 < len(positions) else len(text)
            body = text[start:end].strip()
            entry = DirectiveEntry(
                d_id=d_id,
                title=title,
                file_rel=rel,
                body=body,
                hook_hint=_hook_hint(body),
            )
            idx.entries[d_id] = entry
            file_entries.append(entry)
        idx.by_file[rel] = file_entries
    return idx


def load_directive_bodies(root: Path | None = None) -> dict[str, str]:
    """파일별 전체 본문 (README 포함) — UserPromptSubmit inject 시 사용."""
    root = root or resolve_invest_root()
    ddir = directives_dir(root)
    out: dict[str, str] = {}
    if not ddir.exists():
        return out
    for md in sorted(ddir.glob("*.md")):
        if md.name == "CLAUDE.md":
            continue  # AGENTS.md 로의 symlink — 중복 inject 방지
        rel = md.relative_to(root).as_posix()
        out[rel] = md.read_text(encoding="utf-8")
    return out


HOOK_AUDIT_FNAME = "_hook_audit.log"


def audit_log(hook_name: str, decision: str, reason: str) -> None:
    """telemetry/logs/_hook_audit.log 표준 append. 실패는 silently swallow.

    hook 실행 로그는 감사 증거(telemetry/audit)가 아니라 관측 로그이므로
    telemetry/logs 에 적재한다. INVEST_ROOT 기준 literal (env 경로 override 미경유).
    """
    try:
        ad = resolve_invest_root() / "telemetry" / "logs"
        ad.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(KST).isoformat(timespec="seconds")
        # 한 줄 내 tab/newline 제거 (audit log parsing 단순화)
        safe_reason = reason.replace("\t", " ").replace("\n", " | ")
        with (ad / HOOK_AUDIT_FNAME).open("a", encoding="utf-8") as f:
            f.write(f"{ts}\t{hook_name}\t{decision}\t{safe_reason}\n")
    except Exception:
        pass


# ===========================================================================
# Anti-pattern detection (D-PY-1 / D-SH-1 / D-CFG-1 / D-SEC-1)
# ===========================================================================
# regex 는 conservative — false positive 줄이려 prefix-bound + 길이 최소화.

# D-SEC-1: secret-like literal (prefix-bound, ≥ 길이 최소).
SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("KIS_APP_KEY",    re.compile(r"KIS_APP_KEY\s*=\s*[\"']?PS[A-Za-z0-9]{18,}")),
    ("KIS_APP_SECRET", re.compile(r"KIS_APP_SECRET\s*=\s*[\"']?[A-Za-z0-9+/=]{30,}")),
    ("DART_API_KEY",   re.compile(r"DART_API_KEY\s*=\s*[\"']?[a-f0-9]{40}")),
    ("TELEGRAM_TOKEN", re.compile(r"TELEGRAM_BOT_TOKEN\s*=\s*[\"']?\d{6,}:[A-Za-z0-9_-]{30,}")),
    ("OPENAI_KEY",     re.compile(r"\bsk-[A-Za-z0-9]{32,}\b")),
    ("JWT_LIKE",       re.compile(r"\beyJ[A-Za-z0-9_-]{40,}")),
]

# D-PY-1: .py 헤더 5 줄 내 from __future__ import annotations 부재 검사용.
_FUTURE_RE = re.compile(r"^from __future__ import annotations\s*$", re.MULTILINE)

# D-SH-1: .sh 헤더 5 줄 내 set -uo pipefail (또는 -euo) 부재 검사용.
_SET_RE = re.compile(r"^\s*set\s+-[ue]?u?o\s+pipefail", re.MULTILINE)

# D-CFG-1: governance/*.yaml 새 파일 헤더 5 줄 내 version: + description:.
_VERSION_RE = re.compile(r"^version\s*:", re.MULTILINE)
_DESCRIPTION_RE = re.compile(r"^description\s*:", re.MULTILINE)


def detect_secret_like(content: str) -> list[tuple[str, str]]:
    """secret-like literal 검출. return [(type, snippet), ...]."""
    hits: list[tuple[str, str]] = []
    for name, pat in SECRET_PATTERNS:
        for m in pat.finditer(content):
            # snippet 은 redact — secret 값 자체는 audit log 에 echo 안 함 (D-SEC-6)
            hits.append((name, f"<redacted {name} pattern>"))
    return hits


def detect_py_missing_future(content: str) -> bool:
    """D-PY-1: 헤더 30 줄 내 from __future__ import annotations 가 없으면 True."""
    head = "\n".join(content.splitlines()[:30])
    return _FUTURE_RE.search(head) is None


def detect_sh_missing_set(content: str) -> bool:
    """D-SH-1: 헤더 10 줄 내 set -uo pipefail (또는 -euo) 가 없으면 True."""
    head = "\n".join(content.splitlines()[:10])
    return _SET_RE.search(head) is None


def detect_yaml_missing_header(content: str) -> tuple[bool, bool]:
    """D-CFG-1: 헤더 10 줄 내 version: / description: 부재 여부.
    return (missing_version, missing_description).
    """
    head = "\n".join(content.splitlines()[:10])
    return (_VERSION_RE.search(head) is None, _DESCRIPTION_RE.search(head) is None)


# ===========================================================================
# File path classification — 어느 file 이 어느 directive 의 검사 대상인가
# ===========================================================================

def is_python_source(file_path: str) -> bool:
    """domain/infra/hook .py 만 D-PY-1 대상. tests/ 와 __pycache__ 제외."""
    if not file_path.endswith(".py"):
        return False
    return ("/tests/" not in file_path) and ("__pycache__" not in file_path)


def is_shell_hook(file_path: str) -> bool:
    """.claude/hooks/*.sh 또는 applications/*.sh 만 D-SH-1 대상."""
    if not file_path.endswith(".sh"):
        return False
    return (
        ".claude/hooks/" in file_path
        or "/applications/" in file_path
        or file_path.startswith("applications/")
    )


def is_governance_yaml(file_path: str) -> bool:
    """governance/*.yaml 중 *.local.yaml / *.example.yaml 제외."""
    if not file_path.endswith((".yaml", ".yml")):
        return False
    if "/governance/" not in file_path and not file_path.startswith("governance/"):
        return False
    name = file_path.rsplit("/", 1)[-1]
    if name.endswith(".local.yaml") or name.endswith(".example.yaml"):
        return False
    return True


def is_trail_json(file_path: str) -> bool:
    """operations/{date}/*.json (flat) 만 D-CFG-2 envelope 대상.

    구 operations/{date}/.trails/ 서브디렉토리는 2026-05-12 폐지 — stage 산출물은
    이제 operations/{date}/ 바로 아래 flat 으로 떨어진다 (utils.trail_dir). `.trails/`
    를 요구하던 옛 조건은 매치 0 (silent dead check) 였다.
    """
    has_ops = "/operations/" in file_path or file_path.startswith("operations/")
    return has_ops and file_path.endswith(".json")


def is_markdown(file_path: str) -> bool:
    return file_path.endswith(".md")


# ===========================================================================
# CLI 진입점 (디버그용)
# ===========================================================================
def main() -> int:
    """디버그 CLI — directive index 를 stdout 으로 dump."""
    idx = load_directive_index()
    print(f"[directive-lint] loaded {len(idx.entries)} directives from {len(idx.by_file)} files")
    for d_id in sorted(idx.entries.keys()):
        e = idx.entries[d_id]
        print(f"  {d_id:<14} {e.title}  ({e.file_rel})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
