"""external_signal validator — 검사 A(frontmatter) · D(파일명) 단위테스트."""

from __future__ import annotations

from pathlib import Path

from domains._shared.external_signal.validate import validate_signal_file

_VALID_FRONTMATTER = """\
---
schema: external-signal-v1
ticker: KR:003550
source: "DART"
type: filing
observed_at: "2026-03-26T00:00:00+09:00"
ingested_at: "2026-06-14T12:30:00+09:00"
ingested_by: ingest-external-signal
---

## Fact (paraphrased, opinion-stripped)

- LG(주) 2026-03-26 기업가치제고계획 재공시 (DART@2026-03-26=rcept_no:20260326803162).

## Original (redacted)

DART 공시검색 list.json (corp 003550) 결과 행.
"""


def _write(dir_: Path, name: str = "2026-03-26-001.md", body: str | None = None) -> Path:
    p = dir_ / name
    p.write_text(body if body is not None else _VALID_FRONTMATTER, encoding="utf-8")
    return p


def test_valid_file_passes(tmp_path: Path) -> None:
    res = validate_signal_file(_write(tmp_path))
    assert res.ok, res.errors
    assert res.errors == ()


def test_missing_required_key(tmp_path: Path) -> None:
    body = _VALID_FRONTMATTER.replace(
        "ingested_by: ingest-external-signal\n", ""
    )
    res = validate_signal_file(_write(tmp_path, body=body))
    assert not res.ok
    assert any("ingested_by" in e for e in res.errors)


def test_bad_ticker_format(tmp_path: Path) -> None:
    body = _VALID_FRONTMATTER.replace("ticker: KR:003550", "ticker: KR:12")
    res = validate_signal_file(_write(tmp_path, body=body))
    assert not res.ok
    assert any("ticker" in e for e in res.errors)


def test_non_enum_type(tmp_path: Path) -> None:
    body = _VALID_FRONTMATTER.replace("type: filing", "type: rumor")
    res = validate_signal_file(_write(tmp_path, body=body))
    assert not res.ok
    assert any("type enum" in e for e in res.errors)


def test_bad_filename(tmp_path: Path) -> None:
    res = validate_signal_file(_write(tmp_path, name="2026-03-26-1.md"))
    assert not res.ok
    assert any("파일명" in e for e in res.errors)


def test_filename_observed_at_date_mismatch(tmp_path: Path) -> None:
    # 파일명 date 는 2026-03-26 인데 observed_at 은 2026-05-22
    body = _VALID_FRONTMATTER.replace(
        'observed_at: "2026-03-26T00:00:00+09:00"',
        'observed_at: "2026-05-22T00:00:00+09:00"',
    )
    res = validate_signal_file(_write(tmp_path, body=body))
    assert not res.ok
    assert any("observed_at date" in e for e in res.errors)


def test_no_frontmatter_block(tmp_path: Path) -> None:
    res = validate_signal_file(_write(tmp_path, body="no frontmatter here\n"))
    assert not res.ok
    assert any("frontmatter" in e for e in res.errors)


def test_missing_file(tmp_path: Path) -> None:
    res = validate_signal_file(tmp_path / "2026-03-26-001.md")
    assert not res.ok
    assert any("파일 없음" in e for e in res.errors)


# ── 검사 B (섹션) ─────────────────────────────────────────────────────────


def test_missing_original_section(tmp_path: Path) -> None:
    body = _VALID_FRONTMATTER.split("## Original")[0]  # Original 섹션 절단
    res = validate_signal_file(_write(tmp_path, body=body))
    assert not res.ok
    assert any("## Original" in e for e in res.errors)


def test_missing_fact_section(tmp_path: Path) -> None:
    # frontmatter 만 두고 본문 섹션 제거
    fm_only = _VALID_FRONTMATTER.split("## Fact")[0]
    res = validate_signal_file(_write(tmp_path, body=fm_only))
    assert not res.ok
    assert any("## Fact" in e for e in res.errors)


# ── 검사 C (citation) ─────────────────────────────────────────────────────


def test_broken_citation_token(tmp_path: Path) -> None:
    # '=value' 누락 → 깨진 citation
    body = _VALID_FRONTMATTER.replace(
        "(DART@2026-03-26=rcept_no:20260326803162)", "(DART@2026-03-26)"
    )
    res = validate_signal_file(_write(tmp_path, body=body))
    assert not res.ok
    assert any("citation 형식 위반" in e for e in res.errors)


def test_uncited_number_warning(tmp_path: Path) -> None:
    # citation 없는 숫자 bullet → warning (error 아님)
    body = _VALID_FRONTMATTER.replace(
        "- LG(주) 2026-03-26 기업가치제고계획 재공시 (DART@2026-03-26=rcept_no:20260326803162).",
        "- 자사주 100만주 소각 결정.",
    )
    res = validate_signal_file(_write(tmp_path, body=body))
    assert res.ok, res.errors  # warning 이지 error 아님
    assert any("citation 미부착" in w for w in res.warnings)

