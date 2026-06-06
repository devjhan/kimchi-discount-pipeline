"""
.claude/hooks/_inject_investment_contract.py — UserPromptSubmit inject body.

Called by inject_investment_contract.sh. Reads JSON payload from
INVEST_HOOK_INPUT env var, decides whether to inject investment contract
context, and prints hookSpecificOutput JSON to stdout.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(os.environ["INVEST_ROOT"])
RAW = os.environ.get("INVEST_HOOK_INPUT", "")

try:
    payload = json.loads(RAW) if RAW.strip() else {}
except Exception:
    payload = {}

prompt = (payload.get("prompt") or "")

# ----------------------------------------------------------------------------
# 매치 조건
# ----------------------------------------------------------------------------
SLASH_PATTERNS = [
    "/investment-stage0-regime-labeler",
    "/investment-stage2-quality-lens",
    "/investment-stage4-thesis-auditor",
    "/investment-stage6-brief-author",
    "/investment-audit-process",
    "/investment-audit-outcome",
    "/ingest-external-signal",
]

KEYWORDS = [
    # 한국어 + 영어 도메인 키워드
    "thesis", "macro regime", "quality filter", "quality lens",
    "catalyst", "shadow portfolio", "process audit", "outcome audit",
    "daily brief", "사이즈", "Kelly", "falsifier", "edge source",
    "asymmetry", "특수상황", "지주사", "우선주",
    # alias 직접 인용
    "$TRAIL_TODAY", "$AUDIT_DIR", "$POSITIONS_DIR",
    "$THRESHOLDS_PATH", "$AXIOMS_DIR", "$EXTERNAL_SIGNALS_DIR",
]

matched_skill: str | None = None
for sp in SLASH_PATTERNS:
    if sp in prompt:
        matched_skill = sp.lstrip("/")
        break

keyword_match = any(kw.lower() in prompt.lower() for kw in KEYWORDS)

if not matched_skill and not keyword_match:
    print("{}")
    sys.exit(0)


# ----------------------------------------------------------------------------
# Build inject payload
# ----------------------------------------------------------------------------
def extract_section(text: str, header: str) -> str:
    """## {header} 부터 다음 ## 직전까지."""
    pat = re.compile(rf"(?ms)^## {re.escape(header)}.*?(?=^## |\Z)")
    m = pat.search(text)
    return m.group(0).strip() if m else ""


bootstrap = (ROOT / ".claude/skills/_shared/investment/bootstrap.md").read_text(encoding="utf-8")

sections: list[str] = []
for sec in [
    "Section 1. Source of Truth Hierarchy (ABSOLUTE PRIORITY)",
    "Section 3. Forbidden Language (cross-cutting enforcement)",
    "Section 5. Hard Rules (Cross-cutting)",
    "Section 7. Forbidden Actions (5stone 직역 + 투자 도메인 추가)",
]:
    body = extract_section(bootstrap, sec)
    if body:
        sections.append(body)

header = (
    "# [auto-injected] Investment Pipeline Contract\n"
    "본 텍스트는 .claude/hooks/inject_investment_contract.sh 가 "
    "UserPromptSubmit 시점에 자동 주입한 cross-cutting 규약입니다. "
    "SKILL.md 가 Reference Contract read 를 잊어도 본 contract 는 "
    "이미 컨텍스트에 들어와 있습니다.\n\n"
)

inject = header + "\n\n".join(sections)

out = {
    "hookSpecificOutput": {
        "hookEventName": "UserPromptSubmit",
        "additionalContext": inject,
    }
}
print(json.dumps(out, ensure_ascii=False))
