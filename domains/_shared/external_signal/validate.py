"""external signal 파일 schema validator — 순수 코어 (Path 입력, infra 무의존).

frontmatter + 2-섹션 markdown 산출물(redaction-rules.md SSoT) 의 결정론 검증.
``validate_signal_file(path)`` 가 검사 A/B/C/D 를 모아 ``ValidationResult`` 반환.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from domains._shared.audit.citation import is_valid_citation

# ── frontmatter schema SSoT (redaction-rules.md §4 와 정합) ──────────────────
EXPECTED_SCHEMA = "external-signal-v1"

REQUIRED_FRONTMATTER_KEYS: tuple[str, ...] = (
    "schema",
    "ticker",
    "source",
    "type",
    "observed_at",
    "ingested_at",
    "ingested_by",
)

# redaction-rules.md §4 enum + 실파일에서 사용되는 `filing` 포함 (enum SSoT 정정).
ALLOWED_TYPES: frozenset[str] = frozenset(
    {
        "analyst-note",
        "news",
        "twitter",
        "blog",
        "user-prompt",
        "research-report",
        "filing",
    }
)

_TICKER_RE = re.compile(r"^KR:\d{6}$")
# G20 파일명: {date}-{seq:03d}.md (redaction-rules.md §5)
_FILENAME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-\d{3}\.md$")
# frontmatter 블록: 선두 `---\n ... \n---` + 본문
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", re.DOTALL)

# 본문 citation *substring* 추출용 (CITATION_RE SSoT 는 anchored=전체정합 전용이라
# 본문 내 토큰 스캔엔 부적합 — citation.py 주석이 이 분리를 명시). 추출 후 각 토큰을
# is_valid_citation(anchored SSoT)으로 재검증해 형식을 단일 기준으로 판정한다.
_CITATION_TOKEN = re.compile(r"[A-Za-z0-9_]+@\S+=\S+")
_DIGIT_RE = re.compile(r"\d")


@dataclass(frozen=True)
class ValidationResult:
    """단일 signal 파일 검증 결과. ``ok`` 는 error 0 여부 (warning 은 통과)."""

    path: str
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.errors


def _date_prefix(value: Any) -> str | None:
    """str / datetime.date / datetime.datetime 에서 YYYY-MM-DD prefix 추출."""
    if value is None:
        return None
    if isinstance(value, str):
        return value[:10] if len(value) >= 10 else None
    iso = getattr(value, "isoformat", None)
    if callable(iso):
        return iso()[:10]
    return None


def _parse(
    path: Path,
) -> tuple[dict[str, Any] | None, str, str | None]:
    """(frontmatter dict | None, body, fatal_error | None)."""
    text = path.read_text(encoding="utf-8")
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return None, text, "YAML frontmatter 블록(--- ... ---)을 찾을 수 없음"
    raw_fm, body = m.group(1), m.group(2)
    try:
        import yaml  # type: ignore
    except ImportError:
        return None, body, "PyYAML 미설치 — frontmatter 파싱 불가"
    try:
        fm = yaml.safe_load(raw_fm)
    except yaml.YAMLError as exc:  # type: ignore[attr-defined]
        return None, body, f"frontmatter YAML 파싱 실패: {exc}"
    if not isinstance(fm, dict):
        return None, body, "frontmatter 가 매핑(dict)이 아님"
    return fm, body, None


def _check_frontmatter(
    fm: dict[str, Any], errors: list[str], warnings: list[str]
) -> None:
    """검사 A — 필수키 / 타입 / ticker 형식 / type enum / schema."""
    for key in REQUIRED_FRONTMATTER_KEYS:
        if key not in fm or fm[key] in (None, ""):
            errors.append(f"frontmatter 필수키 누락/빈값: {key}")

    schema = fm.get("schema")
    if isinstance(schema, str) and schema and schema != EXPECTED_SCHEMA:
        warnings.append(f"schema 값이 예상({EXPECTED_SCHEMA})과 다름: {schema!r}")

    ticker = fm.get("ticker")
    if ticker not in (None, ""):
        if not isinstance(ticker, str) or not _TICKER_RE.match(ticker):
            errors.append(f"ticker 형식 위반 (KR:DDDDDD 기대): {ticker!r}")

    sig_type = fm.get("type")
    if sig_type not in (None, ""):
        if not isinstance(sig_type, str) or sig_type not in ALLOWED_TYPES:
            errors.append(
                f"type enum 위반: {sig_type!r} (허용: {sorted(ALLOWED_TYPES)})"
            )


def _check_filename(
    path: Path, fm: dict[str, Any], errors: list[str], warnings: list[str]
) -> None:
    """검사 D — G20 파일명 규약 + observed_at date 일치."""
    name = path.name
    if not _FILENAME_RE.match(name):
        errors.append(f"파일명 G20 규약 위반 (YYYY-MM-DD-NNN.md 기대): {name}")
        return
    file_date = name[:10]
    obs_date = _date_prefix(fm.get("observed_at"))
    if obs_date and obs_date != file_date:
        errors.append(
            f"파일명 date({file_date}) ≠ observed_at date({obs_date})"
        )


def _find_section(body: str, name: str) -> str | None:
    """``## {name}...`` 헤딩의 본문(다음 ``## `` 헤딩 전까지)을 반환. 없으면 None."""
    lines = body.splitlines()
    start: int | None = None
    for i, ln in enumerate(lines):
        s = ln.lstrip()
        if s.startswith("## ") and s[3:].lstrip().startswith(name):
            start = i
            break
    if start is None:
        return None
    out: list[str] = []
    for ln in lines[start + 1 :]:
        if ln.lstrip().startswith("## "):
            break
        out.append(ln)
    return "\n".join(out)


def _check_sections(body: str, errors: list[str], warnings: list[str]) -> None:
    """검사 B — 필수 섹션 ``## Fact`` / ``## Original`` 존재."""
    if _find_section(body, "Fact") is None:
        errors.append("필수 섹션 누락: '## Fact'")
    if _find_section(body, "Original") is None:
        errors.append("필수 섹션 누락: '## Original'")


def _logical_lines(section: str) -> list[str]:
    """연속 continuation 라인(불릿 마커 없이 이어진 줄)을 한 논리 라인으로 병합.

    signal Fact bullet 은 여러 물리 라인에 걸칠 수 있고 citation 이 continuation
    라인에 오기도 한다 → 물리 라인 단위 검사는 false-positive 를 낸다.
    """
    logical: list[str] = []
    cur: list[str] = []

    def flush() -> None:
        if cur:
            logical.append(" ".join(s.strip() for s in cur).strip())
            cur.clear()

    for raw in section.splitlines():
        if not raw.strip():
            flush()
            continue
        stripped = raw.lstrip()
        is_new_bullet = stripped.startswith("-") or stripped.startswith("*")
        if is_new_bullet:
            flush()
            cur.append(raw)
        elif cur:
            cur.append(raw)  # 직전 불릿의 continuation
        else:
            cur.append(raw)  # 독립 prose 라인
            flush()
    flush()
    return logical


def _check_citations(body: str, errors: list[str], warnings: list[str]) -> None:
    """검사 C — Fact 섹션 citation 형식(G7) + 미인용 숫자 heuristic warning."""
    fact = _find_section(body, "Fact")
    if fact is None:
        return  # 섹션 누락은 _check_sections 가 이미 보고
    for line in _logical_lines(fact):
        if not line:
            continue
        tokens = _CITATION_TOKEN.findall(line)
        # '@' 가 있는데 형식에 맞는 citation 토큰이 하나도 없으면 깨진 citation.
        if "@" in line and not tokens:
            errors.append(f"citation 형식 위반 (Fact): {line!r}")
            continue
        # 추출 토큰을 anchored SSoT 로 재검증 (단일 기준).
        for tok in tokens:
            if not is_valid_citation(tok):
                errors.append(f"citation 형식 위반 (Fact): {tok!r}")
        # G7 heuristic: bullet 에 숫자가 있는데 citation 미부착 → warning.
        stripped = line.lstrip()
        is_bullet = stripped.startswith("-") or stripped.startswith("*")
        if is_bullet and not tokens and _DIGIT_RE.search(line):
            warnings.append(f"G7: Fact 항목에 숫자가 있으나 citation 미부착: {line!r}")


def validate_signal_file(path: Path) -> ValidationResult:
    """단일 signal 파일 검증. 코어는 Path 만 받고 infra/도메인 import 0."""
    errors: list[str] = []
    warnings: list[str] = []

    if not path.exists():
        return ValidationResult(str(path), (f"파일 없음: {path}",), ())

    fm, body, fatal = _parse(path)
    if fatal:
        errors.append(fatal)
    if fm is not None:
        _check_frontmatter(fm, errors, warnings)
    _check_filename(path, fm or {}, errors, warnings)
    _check_sections(body, errors, warnings)
    _check_citations(body, errors, warnings)

    return ValidationResult(str(path), tuple(errors), tuple(warnings))
