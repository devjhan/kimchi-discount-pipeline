"""
.claude/hooks/_brief_citation_gate.py — Stage 6 brief-author citation gate.

PostToolUse(Write|Edit) 매처에서 호출. tool_input.file_path 가
`daily-brief.md` 로 끝날 때만 fire. domains._shared.brief_gate.validators.
validate_stage_inputs() 와 본문 unsourced number 정규식 검사를 결합해 G7
citation 규약 위반 시 LLM 에 block + violation list 를 돌려준다.

Stop hook 으로도 재사용 가능 (--stop flag).

Hard guards:
    - G7:  본문 모든 숫자에 source citation 강제
    - G19: forbidden statistical wording (sample size 미충족 시) substring 검사
    - G20: 본 hook 자체는 산출물 작성 안 함 (read-only audit)
    - G21: secret env 노출 없음 (메시지에 secret 변수 echo 안 함)

Exit: 항상 0 — decision 은 hookSpecificOutput JSON 으로 통신.

Performance:
    - file_path 가 daily-brief.md 가 아니면 즉시 sys.exit(0) (short-circuit)
    - validators import 도 short-circuit 후에만 수행
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

KST = timezone(timedelta(hours=9))

# ---------------------------------------------------------------------------
# Read stdin
# ---------------------------------------------------------------------------
ROOT = Path(os.environ.get("INVEST_ROOT", "")).resolve()
RAW = os.environ.get("INVEST_HOOK_INPUT", "")
STOP_MODE = "--stop" in sys.argv[1:]

try:
    payload = json.loads(RAW) if RAW.strip() else {}
except Exception:
    payload = {}

tool_name: str = payload.get("tool_name") or ""
tool_input: dict = payload.get("tool_input") or {}


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------

def _audit_log(decision: str, reason: str) -> None:
    try:
        # hook 관측 로그 → telemetry/logs (감사 증거 telemetry/audit 와 분리, env 미경유)
        log_dir = ROOT / "telemetry" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / "_hook_audit.log"
        ts = datetime.now(KST).isoformat(timespec="seconds")
        with log_path.open("a", encoding="utf-8") as f:
            f.write(
                f"{ts}\tbrief_citation_gate{':stop' if STOP_MODE else ''}\t{decision}\t{reason}\n"
            )
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Short-circuit: only act on daily-brief.md
# ---------------------------------------------------------------------------

def _target_brief_path() -> Path | None:
    """
    PostToolUse 의 tool_input 에서 daily-brief.md 경로를 찾는다.
    Stop mode 에서는 $DAILY_BRIEF_PATH fallback (legacy $TRAIL_TODAY 도 호환).

    2026-05-12 이후: brief 는 operations/{date}/daily-brief.md (DATE 디렉토리
    루트) 에 위치.  legacy $TRAIL_TODAY/daily-brief.md (.trails/ 안) 는 더 이상
    산출되지 않지만 historical artifact 검사를 위해 fallback 유지.
    """
    fp = tool_input.get("file_path") or ""
    if fp and fp.endswith("daily-brief.md"):
        return Path(fp)
    if STOP_MODE:
        brief_path = os.environ.get("DAILY_BRIEF_PATH")
        if brief_path:
            cand = Path(brief_path)
            if cand.exists():
                return cand
        # legacy fallback — pre-2026-05-12 산출물
        trail = os.environ.get("TRAIL_TODAY")
        if trail:
            cand = Path(trail) / "daily-brief.md"
            if cand.exists():
                return cand
    return None


brief_path = _target_brief_path()
if brief_path is None:
    sys.exit(0)

if not STOP_MODE and tool_name not in {"Write", "Edit"}:
    sys.exit(0)


# ---------------------------------------------------------------------------
# Validate stage inputs (G7 envelope + citation regex)
# ---------------------------------------------------------------------------

if not ROOT or not ROOT.exists():
    # ROOT 미설정이면 silently 통과 — sessionStart hook 로딩 실패 방어
    sys.exit(0)

sys.path.insert(0, str(ROOT))
try:
    from domains._shared.brief_gate.validators import (  # type: ignore
        validate_stage_inputs,
        CITATION_RE,
    )
except Exception:
    sys.exit(0)

trail_dir_str = os.environ.get("TRAIL_TODAY")
violations: list[str] = []
if trail_dir_str:
    trail_dir = Path(trail_dir_str)
    if trail_dir.exists():
        try:
            _, vio = validate_stage_inputs(trail_dir)
            violations.extend(vio)
        except Exception as exc:  # noqa: BLE001
            violations.append(
                f"validate_stage_inputs raised {type(exc).__name__}: {exc}"
            )


# ---------------------------------------------------------------------------
# Inline brief body checks — unsourced numbers + forbidden language
# ---------------------------------------------------------------------------

# 숫자 패턴: 정수/소수/퍼센트 — 단, 같은 줄에 citation 형식 (`SRC@ts=val`) 또는
# fenced code block 내부면 제외. citation regex 와 동일한 SOURCE@TS=VALUE 패턴.
_NUMBER_RE = re.compile(r"(?<![\w.])-?\d+(?:\.\d+)?(?:%|%p)?(?![\w.])")
_DATE_LIKE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_HEADER_OR_LIST_PREFIX = re.compile(r"^\s*[#>\-*|]+")

FORBIDDEN_WORDING = [
    "should buy",
    "should sell",
    "looks bullish",
    "looks bearish",
    "guaranteed",
    "sure thing",
    "no-brainer",
    "must hold",
    "set to rise",
    "set to fall",
    "outperformed the market",
    "alpha confirmed",
    "strategy proven",
    "beats benchmark",
]


def _scan_brief_body(p: Path) -> list[str]:
    """본문 line 단위 검사. 산출 stage 인용 형식이 없는 숫자 / 금칙어 substring."""
    out: list[str] = []
    try:
        text = p.read_text(encoding="utf-8")
    except FileNotFoundError:
        return [f"daily-brief.md 파일 미존재: {p}"]
    in_code_fence = False
    for ln, raw in enumerate(text.splitlines(), start=1):
        stripped = raw.strip()
        if stripped.startswith("```"):
            in_code_fence = not in_code_fence
            continue
        if in_code_fence:
            continue
        # forbidden wording substring (case-insensitive)
        low = stripped.lower()
        for phrase in FORBIDDEN_WORDING:
            if phrase in low:
                out.append(
                    f"L{ln}: forbidden_language hit '{phrase}' — bootstrap.md Section 3 위반"
                )
        # citation 검사: 줄에 SRC@ts=val 형식이 1개라도 있으면 통과
        has_citation = bool(re.search(r"[A-Za-z0-9_]+@\S+=\S+", stripped))
        # 헤더 / 표 헤더 / disclaimer 등 단순 텍스트는 숫자 검사 면제 패턴
        # — date-like 토큰만 있는 줄 / 표 구분자 줄 면제
        if has_citation:
            continue
        nums = _NUMBER_RE.findall(stripped)
        if not nums:
            continue
        # 표 구분자 줄 (`|---|---|`) 면제
        if set(stripped) <= set("|-: "):
            continue
        # 모든 숫자가 date 일부면 면제 (e.g., '2026-05-09' 헤더)
        if all(_DATE_LIKE_RE.match(tok) for tok in [t for t in stripped.split() if "-" in t]):
            continue
        # 표 시작 줄 / 헤더가 단순 month-year 표기일 가능성: 유연하게 면제
        # — 본 helper 는 보수적으로 violation 보고, LLM 이 false-positive 시 정정
        out.append(
            f"L{ln}: unsourced number(s) {nums} — citation 'SRC@ts=val' 누락 (G7)"
        )
    return out


body_violations = _scan_brief_body(brief_path)
violations.extend(body_violations)


# ---------------------------------------------------------------------------
# Decision
# ---------------------------------------------------------------------------

if not violations:
    _audit_log("ALLOW", f"brief={brief_path.name} clean")
    sys.exit(0)

# Truncate to keep hook output reasonable
SHOWN = violations[:30]
extra = len(violations) - len(SHOWN)

reason_lines = [
    f"[brief-citation-gate] {len(violations)} violation(s) detected in {brief_path.name}.",
    "G7 (citation) / G19 (forbidden language) 위반은 자동 redact 대상이다.",
    "각 violation 에 해당하는 본문 라인을 helper 산출물 인용 형식 "
    "'SRC@ISO_TS=VALUE' 로 수정하거나 'omitted (reason)' 처리하라.",
    "",
] + [f"  - {v}" for v in SHOWN]
if extra > 0:
    reason_lines.append(f"  ... +{extra} more")
reason = "\n".join(reason_lines)

_audit_log(
    "BLOCK" if not STOP_MODE else "STOP_BLOCK",
    f"brief={brief_path.name} violations={len(violations)}",
)

if STOP_MODE:
    out = {"decision": "block", "reason": reason}
else:
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
