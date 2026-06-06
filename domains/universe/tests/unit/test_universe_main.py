"""universe.main CLI (Run 4) — envelope 정합 + exit code + legacy schema 호환."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from domains.universe.main import SCHEMA_VERSION, main


@pytest.fixture(autouse=True)
def _isolate_audit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """universe main 의 ViolationLog 가 audit_dir() (= telemetry/audit) 에 기록되므로
    AUDIT_DIR 를 tmp 로 격리 — 실제 telemetry/audit 오염 방지.
    """
    monkeypatch.setenv("AUDIT_DIR", str(tmp_path / "_audit"))


@pytest.mark.unit
def test_main_dry_run_produces_legacy_compatible_envelope(tmp_path: Path) -> None:
    """`--dry-run --trail-dir <tmp>` 실행 후 01-universe.json 의 envelope 키 검증.

    legacy ``domains.alpha_factory.universe`` 와 동일 schema 보장:
    - schema / generated_at / date / config_path / config_version
    - stats / entries / warnings / skipped_sources
    """
    exit_code = main(["--dry-run", "--trail-dir", str(tmp_path), "--date", "2026-05-17"])
    assert exit_code == 0

    out_path = tmp_path / "01-universe.json"
    assert out_path.exists()
    envelope = json.loads(out_path.read_text(encoding="utf-8"))

    # envelope 최상위 키 (legacy 와 동일)
    expected_keys = {
        "schema",
        "generated_at",
        "date",
        "config_path",
        "config_version",
        "stats",
        "entries",
        "warnings",
        "skipped_sources",
    }
    assert expected_keys.issubset(envelope.keys())
    assert envelope["schema"] == SCHEMA_VERSION
    assert envelope["date"] == "2026-05-17"
    # config_path → sources.yaml (legacy 는 thresholds.yaml — 의도된 변경)
    assert envelope["config_path"].endswith("sources.yaml")

    # stats 최소 필드
    stats = envelope["stats"]
    assert "total" in stats
    assert "by_source_category" in stats
    assert "excluded" in stats
    assert "dry_run" in stats
    assert stats["dry_run"] is True
    assert stats["total"] == 0

    # entries / warnings / skipped_sources 는 list
    assert isinstance(envelope["entries"], list)
    assert isinstance(envelope["warnings"], list)
    assert isinstance(envelope["skipped_sources"], list)


@pytest.mark.unit
def test_main_entries_have_legacy_compatible_fields(tmp_path: Path) -> None:
    """entries 가 비어 있더라도 dataclass.asdict() 직렬화가 legacy 구조와 호환.

    UniverseEntry 직렬화 결과: ticker / name / source_category / inclusion_reason /
    fetched_at / source_citation / metadata — legacy alpha_factory/universe.py:58-66
    의 UniverseEntry 와 동일 (frozen 으로 강화한 것 외).
    """
    from dataclasses import asdict

    from domains.universe.domain.entry import UniverseEntry

    sample = UniverseEntry(
        ticker="KR:001",
        name="test",
        source_category="manual_addition",
        inclusion_reason="r",
        fetched_at="t",
        source_citation="c",
    )
    serialized = asdict(sample)
    assert set(serialized.keys()) == {
        "ticker", "name", "source_category", "inclusion_reason",
        "fetched_at", "source_citation", "metadata",
    }
    # round-trip via JSON 정상
    assert json.loads(json.dumps(serialized)) == serialized


@pytest.mark.unit
def test_main_emits_handoff_summary(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """stdout 의 D-Q-6 handoff 1줄 (``[stage1-universe] ... -> path``)."""
    main(["--dry-run", "--trail-dir", str(tmp_path), "--date", "2026-05-17"])
    captured = capsys.readouterr()
    assert "[stage1-universe]" in captured.out
    assert "date=2026-05-17" in captured.out
    assert "01-universe.json" in captured.out
    assert "mode=dry-run" in captured.out


@pytest.mark.unit
def test_main_writes_collision_safe_output(tmp_path: Path) -> None:
    """G20 — 같은 경로 두 번 호출 시 .{N}.json suffix 자동 부여."""
    main(["--dry-run", "--trail-dir", str(tmp_path), "--date", "2026-05-17"])
    main(["--dry-run", "--trail-dir", str(tmp_path), "--date", "2026-05-17"])
    files = sorted(p.name for p in tmp_path.iterdir() if p.name.startswith("01-universe"))
    # 01-universe.json + 01-universe.1.json (또는 .2.json) — 최소 2개
    assert len(files) >= 2
