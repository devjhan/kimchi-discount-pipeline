"""
.claude/hooks/_pre_env_guard.py — PreToolUse .env direct-access guard.

Called by pre_env_guard.sh. Blocks any Claude Code tool call that directly
targets or textually references the secret dotenv (.env / .env.local / …),
so secrets never surface through the agent toolchain. Template files
(.env.example / .env.template) are allowed — git-tracked, no secret content.

Blocked patterns:
  - Read(file_path → *.env, *.env.local, …)
  - Write / Edit(file_path → *.env, …)
  - Bash(command containing ".env" literal)

Legitimate runtime reads (load_env_file() inside Python domain scripts) go
through Python's own file I/O, not through these Claude Code tools, so they
are unaffected.

Exit: always 0 — decision communicated via hookSpecificOutput JSON.
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(os.environ["INVEST_ROOT"])
RAW = os.environ.get("INVEST_HOOK_INPUT", "")

KST = timezone(timedelta(hours=9))
# `.env` 자체 + suffix 변형 (e.g., `.env.local`, `.env.bak`) 은 차단,
# 단 `.example` / `.template` 은 placeholder template 이라 허용 (agent 가 format
# 인지 / `cp` 베이스로 사용). secret 보호의 핵심은 actual secret 파일 차단이며,
# template 은 git 추적 대상으로 노출 영향 없음.
# `\b` 가 load-bearing: `.env`/`.env.local` 차단, `.env.example`/`.env.template`
# 허용, `.environment` 는 비매치 (env 뒤 word char 가 \b 를 무효화).
_ENV_SECRET_RE = re.compile(r"\.env\b(?!\.(?:example|template)\b)")

# ---------------------------------------------------------------------------
# Parse stdin payload
# ---------------------------------------------------------------------------
try:
    payload = json.loads(RAW) if RAW.strip() else {}
except Exception:
    payload = {}

tool_name: str = payload.get("tool_name") or ""
tool_input: dict = payload.get("tool_input") or {}

# ---------------------------------------------------------------------------
# Audit log helper
# ---------------------------------------------------------------------------

def _audit_log(decision: str, reason: str) -> None:
    try:
        # hook 관측 로그 → telemetry/logs (감사 증거 telemetry/audit 와 분리, env 미경유)
        log_dir = ROOT / "telemetry" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / "_hook_audit.log"
        ts = datetime.now(KST).isoformat(timespec="seconds")
        log_path.open("a", encoding="utf-8").write(
            f"{ts}\tpre_env_guard\t{decision}\t{reason}\n"
        )
    except Exception:
        pass  # 감사 로그 실패가 guard 자체를 막아선 안 됨


# ---------------------------------------------------------------------------
# Scope check: Read, Write, Edit, Bash
# ---------------------------------------------------------------------------

GUARDED_TOOLS = {"Read", "Write", "Edit", "Bash"}

if tool_name not in GUARDED_TOOLS:
    sys.exit(0)

# ---------------------------------------------------------------------------
# Detection logic
# ---------------------------------------------------------------------------

def _file_path_hits(ti: dict) -> bool:
    fp = ti.get("file_path") or ""
    return bool(fp and _ENV_SECRET_RE.search(fp))


def _bash_command_hits(ti: dict) -> bool:
    cmd = ti.get("command") or ""
    return bool(cmd and _ENV_SECRET_RE.search(cmd))


hit = False
if tool_name in {"Read", "Write", "Edit"}:
    hit = _file_path_hits(tool_input)
elif tool_name == "Bash":
    hit = _bash_command_hits(tool_input)

if not hit:
    sys.exit(0)

# ---------------------------------------------------------------------------
# Block
# ---------------------------------------------------------------------------

reason_lines = [
    f"[env-guard] BLOCK: {tool_name} 도구가 .env 에 직접 접근하려 했습니다.",
    "  .env 는 API key / secret token 을 담고 있어 agent toolchain 에 노출되면 안 됩니다.",
    "  secret 값이 필요하면 load_env_file() (infrastructure._common.utils) 을 Python 코드 내부에서 호출하세요.",
    "  agent 가 secret 값 자체를 읽을 필요는 없습니다 — 도메인 helper 가 파일 파싱을 대신합니다.",
]
reason = "\n".join(reason_lines)

_audit_log("BLOCK", f"tool={tool_name}")

out = {
    "hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": reason,
    }
}
print(json.dumps(out, ensure_ascii=False))
sys.exit(0)
