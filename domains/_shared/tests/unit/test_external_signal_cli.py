"""external_signal validator CLI — exit code 게이트 동작 검증."""

from __future__ import annotations

from pathlib import Path

import pytest

from domains._shared.external_signal.__main__ import main

_VALID = """\
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

- 재공시 (DART@2026-03-26=rcept_no:20260326803162).

## Original (redacted)

list.json 행.
"""


def _write_signal(intake: Path, ticker: str = "KR_003550") -> Path:
    d = intake / ticker
    d.mkdir(parents=True, exist_ok=True)
    p = d / "2026-03-26-001.md"
    p.write_text(_VALID, encoding="utf-8")
    return p


def test_validate_single_valid_returns_0(tmp_path: Path) -> None:
    p = _write_signal(tmp_path)
    assert main(["--validate", str(p)]) == 0


def test_validate_single_invalid_returns_1(tmp_path: Path) -> None:
    p = tmp_path / "bad.md"  # 파일명 규약 위반 + frontmatter 없음
    p.write_text("garbage\n", encoding="utf-8")
    assert main(["--validate", str(p)]) == 1


def test_validate_all_valid_returns_0(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    intake = tmp_path / "telemetry" / "external_signals"
    _write_signal(intake)
    monkeypatch.setenv("EXTERNAL_SIGNAL_INTAKE_DIR", str(intake))
    assert main(["--validate-all"]) == 0


def test_validate_all_failing_returns_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    intake = tmp_path / "telemetry" / "external_signals"
    d = intake / "KR_003550"
    d.mkdir(parents=True, exist_ok=True)
    (d / "2026-03-26-001.md").write_text("no frontmatter\n", encoding="utf-8")
    monkeypatch.setenv("EXTERNAL_SIGNAL_INTAKE_DIR", str(intake))
    assert main(["--validate-all"]) == 1


def test_validate_all_empty_dir_graceful(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    intake = tmp_path / "telemetry" / "external_signals"
    monkeypatch.setenv("EXTERNAL_SIGNAL_INTAKE_DIR", str(intake))
    assert main(["--validate-all"]) == 0  # 디렉토리 미존재 → graceful


def test_requires_an_argument(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        main([])  # mutually exclusive required → argparse SystemExit(2)
