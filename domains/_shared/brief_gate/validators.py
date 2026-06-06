"""
domains/_shared/brief_gate/validators.py — Stage 6 input validator.

`investment-stage6-brief-author` skill 이 brief 합성 전 Stage 0~5 산출물의
schema + G7 citation 적합성을 fail-fast 검증하기 위한 helper.

본 module은 LLM 산출물을 만들지 않는다 — 검증만 수행한다. violation 발견 시
raise 하지 않고 list로 반환하므로, skill은 violation note section을 brief
본문에 첨부한 채 산출을 계속할 수 있다 (강한 강제는 audit-process skill 책임).

Hard guards:
    - G7: 모든 entry citation 이 `{source}@{ts}={value}` 정규식 매치 — 위반 시 violation 추가
    - G20: 본 module은 산출물 작성 안 함 (read-only)

Usage:
    from domains.brief_gate import validate_stage_inputs
    merged, violations = validate_stage_inputs(trail_dir)
    if violations:
        # skill: brief에 violation note section 첨부
        ...
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from domains._shared.audit.citation import CITATION_RE

# G7 표준 citation 정규식 — `SOURCE@ISO_TS=VALUE`. SSoT 는
# `domains/_shared/audit/citation.py`. 본 module 은 back-compat 위해 재export
# (brief_gate.__init__ 의 __all__ + brief_citation_gate 훅이 transitively import).

# 필수 산출물 (Stage 0/1/2/3/4/5 deterministic + LLM skill)
REQUIRED_FILES: tuple[str, ...] = (
    "00-macro-regime.json",
    "01-universe.json",
    "02-quality-filter.json",
    "03-catalyst-events.json",
    "04-thesis-candidates.json",
    "05-sizing-recommendation.json",
)

# 옵셔널 (LLM lens / 보조 산출물 — 미존재 시 violation 아님)
OPTIONAL_FILES: tuple[str, ...] = (
    "02-quality-lens.json",
    "02-fin-fetch.json",
)

# 각 stage 별 entry list 가 있는 키 — citation 검사 대상
ENTRY_KEYS: dict[str, str] = {
    "01-universe.json": "entries",
    "02-quality-filter.json": "verdicts",
    "03-catalyst-events.json": "candidates",
}


def _load_json(p: Path) -> tuple[dict[str, Any] | None, str | None]:
    """JSON load. 실패 시 (None, error_msg)."""
    try:
        with p.open("r", encoding="utf-8") as f:
            return json.load(f), None
    except FileNotFoundError:
        return None, f"file not found: {p.name}"
    except json.JSONDecodeError as exc:
        return None, f"{p.name}: JSON decode fail — {exc}"
    except Exception as exc:  # noqa: BLE001
        return None, f"{p.name}: {type(exc).__name__} — {exc}"


def _check_envelope(name: str, payload: dict[str, Any]) -> list[str]:
    """top-level schema / generated_at / date 키 존재 여부."""
    out: list[str] = []
    for k in ("schema", "generated_at", "date"):
        if k not in payload:
            out.append(f"{name}: missing top-level '{k}'")
    return out


def _check_citation(name: str, payload: dict[str, Any], entry_key: str) -> list[str]:
    """
    payload[entry_key] 의 각 entry 가 비어있지 않은 citations / source_citation
    필드를 갖고, 모두 G7 정규식 매치하는지.
    """
    out: list[str] = []
    entries = payload.get(entry_key)
    if not isinstance(entries, list):
        # 빈 list 자체는 Default = No Action 이라 violation 아님
        return out
    for i, e in enumerate(entries):
        if not isinstance(e, dict):
            out.append(f"{name}.{entry_key}[{i}]: not a dict")
            continue
        # verdict=unknown → financial data 미수집 (cache miss). metrics={} 이므로
        # cite할 숫자가 없어 G7 citation 요건 면제. quality_filter.py G8 참조.
        # NOTE: verdict=caution (필수 enrichment 누락 / 불량 프로파일) 은 면제 아님 —
        # 실제 snapshot citations 보유. unknown 만 exact-match 로 면제.
        if e.get("verdict") == "unknown":
            continue
        cites: list[Any] = []
        if "citations" in e:
            v = e.get("citations") or []
            if isinstance(v, list):
                cites.extend(v)
        if "source_citation" in e:
            v = e.get("source_citation")
            if v:
                cites.append(v)
        if not cites:
            out.append(
                f"{name}.{entry_key}[{i}] (ticker={e.get('ticker','?')}): "
                f"citation 누락 (G7 위반)"
            )
            continue
        for c in cites:
            if not isinstance(c, str) or not CITATION_RE.match(c):
                out.append(
                    f"{name}.{entry_key}[{i}] (ticker={e.get('ticker','?')}): "
                    f"citation G7 정규식 불일치 — {c!r}"
                )
                break
    return out


def _check_sizing_caps(name: str, payload: dict[str, Any]) -> list[str]:
    """Stage 5 산출물의 cap_violations 필드 비어있어야 통과."""
    out: list[str] = []
    cv = payload.get("cap_violations")
    if cv:
        out.append(f"{name}: cap_violations non-empty — {cv!r}")
    return out


def validate_stage_inputs(
    trail_dir: Path,
) -> tuple[dict[str, Any], list[str]]:
    """
    Stage 0~5 산출물의 schema + G7 citation + date 일치를 검사.

    Args:
        trail_dir: $TRAIL_TODAY 디렉토리 (operations/{YYYY-MM-DD}/).

    Returns:
        (merged, violations).
        merged 는 각 파일명 → loaded payload dict (옵셔널 파일은 미존재 시 None).
        violations 는 위반 메시지 list (비어있으면 통과).

    raise 하지 않음. skill 은 violations 가 있어도 brief 본문에 note 첨부 후 진행.
    """
    merged: dict[str, Any] = {}
    violations: list[str] = []

    # 필수 파일 load
    for fname in REQUIRED_FILES:
        payload, err = _load_json(trail_dir / fname)
        if err:
            violations.append(err)
            merged[fname] = None
            continue
        merged[fname] = payload
        violations.extend(_check_envelope(fname, payload))

    # 옵셔널 파일 load (없으면 None)
    for fname in OPTIONAL_FILES:
        p = trail_dir / fname
        if not p.exists():
            merged[fname] = None
            continue
        payload, err = _load_json(p)
        if err:
            # 옵셔널이라도 깨진 JSON 은 violation
            violations.append(err)
            merged[fname] = None
            continue
        merged[fname] = payload
        violations.extend(_check_envelope(fname, payload))

    # date 일치 검증 (필수 파일 기준)
    dates: set[str] = set()
    for fname in REQUIRED_FILES:
        p = merged.get(fname)
        if isinstance(p, dict) and p.get("date"):
            dates.add(str(p["date"]))
    if len(dates) > 1:
        violations.append(
            f"date 불일치: {sorted(dates)} — 모든 stage 산출물의 date 가 같아야 함"
        )

    # G7 citation 검사 (entry list 가 있는 stage 만)
    for fname, entry_key in ENTRY_KEYS.items():
        p = merged.get(fname)
        if isinstance(p, dict):
            violations.extend(_check_citation(fname, p, entry_key))

    # Stage 5 cap_violations 비어있어야 통과
    p5 = merged.get("05-sizing-recommendation.json")
    if isinstance(p5, dict):
        violations.extend(_check_sizing_caps("05-sizing-recommendation.json", p5))

    return merged, violations


__all__ = ["validate_stage_inputs", "CITATION_RE", "REQUIRED_FILES", "OPTIONAL_FILES"]
