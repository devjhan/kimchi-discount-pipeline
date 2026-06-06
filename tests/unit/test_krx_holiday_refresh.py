"""tests/unit/test_krx_holiday_refresh.py — KRX holiday refresh helper (pure functions)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from infrastructure.krx.refresh_holidays import (
    FetchError,
    diff_holidays,
    load_existing_json,
    merge_holidays,
    write_atomically,
)

pytestmark = pytest.mark.unit


# ============================================================
# merge_holidays
# ============================================================

def test_merge_holidays_union_dedup_sort():
    existing = {"holidays": ["2026-01-01"], "_meta": {}, "_comment": ""}
    fetched = ["2026-01-01", "2026-02-16"]
    result = merge_holidays(existing, fetched, "src@2026-05-09=url", "2026-05-09")
    assert result["holidays"] == ["2026-01-01", "2026-02-16"]


def test_merge_holidays_updates_meta():
    existing = {"holidays": [], "_meta": {"stale_after_months": 6}, "_comment": ""}
    result = merge_holidays(existing, [], "KRX@2026-05-09=url", "2026-05-09")
    assert result["_meta"]["last_verified_date"] == "2026-05-09"
    assert result["_meta"]["source"] == "KRX@2026-05-09=url"


def test_merge_holidays_preserves_stale_after_months():
    existing = {"holidays": [], "_meta": {"stale_after_months": 12}}
    result = merge_holidays(existing, [], "src", "2026-05-09")
    assert result["_meta"]["stale_after_months"] == 12


def test_merge_holidays_default_stale_after_when_missing():
    existing = {"holidays": [], "_meta": {}}
    result = merge_holidays(existing, [], "src", "2026-05-09")
    assert result["_meta"]["stale_after_months"] == 6


def test_merge_holidays_empty_existing():
    existing = {"_comment": "", "_meta": {}, "holidays": []}
    result = merge_holidays(existing, ["2026-01-01"], "src", "2026-05-09")
    assert result["holidays"] == ["2026-01-01"]


def test_merge_holidays_empty_fetched():
    existing = {"holidays": ["2026-01-01"], "_meta": {}}
    result = merge_holidays(existing, [], "src", "2026-05-09")
    assert result["holidays"] == ["2026-01-01"]


def test_merge_holidays_existing_unchanged():
    existing = {"holidays": ["2026-01-01"], "_meta": {"stale_after_months": 6}}
    merge_holidays(existing, ["2026-02-16"], "src", "2026-05-09")
    assert existing["holidays"] == ["2026-01-01"]


def test_diff_holidays_added_removed():
    existing = {"holidays": ["2026-01-01", "2026-03-01"]}
    merged = {"holidays": ["2026-01-01", "2026-02-16"]}
    d = diff_holidays(existing, merged)
    assert d["added"] == ["2026-02-16"]
    assert d["removed"] == ["2026-03-01"]
    assert d["total_before"] == 2
    assert d["total_after"] == 2


# ============================================================
# load_existing_json
# ============================================================

def test_load_existing_json_missing_file(tmp_path: Path):
    p = tmp_path / "no_such_file.json"
    result = load_existing_json(p)
    assert result["holidays"] == []
    assert "_meta" in result


def test_load_existing_json_valid(tmp_path: Path):
    p = tmp_path / "holidays.json"
    payload = {"holidays": ["2026-01-01"], "_meta": {"stale_after_months": 6}}
    p.write_text(json.dumps(payload), encoding="utf-8")
    result = load_existing_json(p)
    assert result["holidays"] == ["2026-01-01"]


def test_load_existing_json_invalid_json(tmp_path: Path):
    p = tmp_path / "bad.json"
    p.write_text("{ not valid json", encoding="utf-8")
    with pytest.raises(FetchError, match="파싱 실패"):
        load_existing_json(p)


# ============================================================
# write_atomically
# ============================================================

def test_write_atomically_creates_file(tmp_path: Path):
    p = tmp_path / "holidays.json"
    payload = {"holidays": ["2026-01-01"], "_meta": {}}
    write_atomically(p, payload)
    assert p.exists()
    loaded = json.loads(p.read_text(encoding="utf-8"))
    assert loaded["holidays"] == ["2026-01-01"]


def test_write_atomically_creates_bak_when_existing(tmp_path: Path):
    p = tmp_path / "holidays.json"
    old = {"holidays": ["2025-01-01"], "_meta": {}}
    p.write_text(json.dumps(old), encoding="utf-8")
    new = {"holidays": ["2026-01-01"], "_meta": {}}
    write_atomically(p, new)
    bak = tmp_path / "holidays.json.bak"
    assert bak.exists()
    loaded_bak = json.loads(bak.read_text(encoding="utf-8"))
    assert loaded_bak["holidays"] == ["2025-01-01"]


def test_write_atomically_no_tmp_leftover(tmp_path: Path):
    p = tmp_path / "holidays.json"
    write_atomically(p, {"holidays": [], "_meta": {}})
    tmp = tmp_path / "holidays.json.tmp"
    assert not tmp.exists()


# ============================================================
# CLI dry-run (subprocess — no network)
# ============================================================

def test_dry_run_does_not_write(tmp_path: Path):
    # holidays.json with known content
    p = tmp_path / "holidays.json"
    original = {"holidays": ["2026-01-01"], "_meta": {"stale_after_months": 6}}
    p.write_text(json.dumps(original), encoding="utf-8")

    # Monkeypatch fetch by calling with --dry-run and invalid endpoint
    # The dry-run should fail at fetch (exit 1) — file should remain unchanged.
    # We test the pure-function path by patching the module in-process.
    from unittest.mock import patch

    from infrastructure.krx.refresh_holidays import main

    # Patch fetch to return empty list (simulating successful fetch)
    with patch(
        "infrastructure.krx.refresh_holidays.fetch_krx_holidays",
        return_value=([], "MOCK@2026-05-09=url"),
    ):
        rc = main(["--dry-run", "--holidays-path", str(p), "--years", "2026"])

    assert rc == 0
    # File must be unchanged (dry-run)
    loaded = json.loads(p.read_text(encoding="utf-8"))
    assert loaded["holidays"] == ["2026-01-01"]


def test_real_run_writes_file(tmp_path: Path):
    p = tmp_path / "holidays.json"
    original = {"holidays": ["2026-01-01"], "_meta": {"stale_after_months": 6}}
    p.write_text(json.dumps(original), encoding="utf-8")

    from unittest.mock import patch

    from infrastructure.krx.refresh_holidays import main

    with patch(
        "infrastructure.krx.refresh_holidays.fetch_krx_holidays",
        return_value=(["2026-01-01", "2026-02-16"], "MOCK@2026-05-09=url"),
    ):
        rc = main(["--holidays-path", str(p), "--years", "2026"])

    assert rc == 0
    loaded = json.loads(p.read_text(encoding="utf-8"))
    assert "2026-02-16" in loaded["holidays"]
    assert loaded["_meta"]["last_verified_date"] is not None


def test_fetch_failure_returns_exit_1(tmp_path: Path):
    p = tmp_path / "holidays.json"
    p.write_text(json.dumps({"holidays": [], "_meta": {}}), encoding="utf-8")

    from unittest.mock import patch

    from infrastructure.krx.refresh_holidays import FetchError, main

    with patch(
        "infrastructure.krx.refresh_holidays.fetch_krx_holidays",
        side_effect=FetchError("network down"),
    ):
        rc = main(["--holidays-path", str(p), "--years", "2026"])

    assert rc == 1
    # File unchanged
    loaded = json.loads(p.read_text(encoding="utf-8"))
    assert loaded["holidays"] == []


# ============================================================
# annual self-skip gate (D-2 — --years 미지정 auto 모드)
# ============================================================
def test_auto_mode_skips_when_current_year_cached(tmp_path: Path):
    """--years 미지정 + 현재 연도 cache → fetch self-skip (daily 무조건 호출 OK)."""
    from datetime import datetime
    from unittest.mock import patch

    from infrastructure._common.utils import KST
    from infrastructure.krx.refresh_holidays import main

    cur = datetime.now(KST).year
    p = tmp_path / "holidays.json"
    p.write_text(json.dumps({"holidays": [f"{cur}-01-01"], "_meta": {}}), encoding="utf-8")
    with patch(
        "infrastructure.krx.refresh_holidays.fetch_krx_holidays",
        side_effect=AssertionError("fetch must not run when current year cached"),
    ):
        rc = main(["--holidays-path", str(p)])  # no --years → auto 모드
    assert rc == 0


def test_auto_mode_fetches_when_current_year_missing(tmp_path: Path):
    """--years 미지정 + 현재 연도 미cache → gate 통과 후 fetch 진행."""
    from datetime import datetime
    from unittest.mock import patch

    from infrastructure._common.utils import KST
    from infrastructure.krx.refresh_holidays import main

    cur = datetime.now(KST).year
    p = tmp_path / "holidays.json"
    p.write_text(json.dumps({"holidays": ["2000-01-01"], "_meta": {}}), encoding="utf-8")
    with patch(
        "infrastructure.krx.refresh_holidays.fetch_krx_holidays",
        return_value=([f"{cur}-12-25"], "MOCK@t=url"),
    ):
        rc = main(["--holidays-path", str(p)])
    assert rc == 0
    loaded = json.loads(p.read_text(encoding="utf-8"))
    assert f"{cur}-12-25" in loaded["holidays"]
