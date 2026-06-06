"""macro.main + indicators + classify_regime — Run 7 envelope parity + behavior."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from domains.macro.application.regime_classify import classify_regime
from domains.macro.domain.regime import IndicatorResult
from domains.macro.main import SCHEMA_VERSION, main


def _ind(value: float | None, *, label: str = "x", percentile: float | None = None) -> IndicatorResult:
    return IndicatorResult(
        indicator="test",
        value=value,
        value_label=label,
        source_citation="FRED@t=v" if value is not None else None,
        percentile=percentile,
        skip_reason=None if value is not None else "skipped",
    )


# ----------------------------------------------------------------------
# classify_regime
# ----------------------------------------------------------------------


@pytest.mark.unit
def test_classify_all_skipped_returns_unknown() -> None:
    result = classify_regime({}, {})
    assert result.regime == "unknown"
    assert result.votes == ()


@pytest.mark.unit
def test_classify_yield_curve_inverted_late_cycle() -> None:
    result = classify_regime(
        {"yield_curve": _ind(-0.2)},
        {"thresholds": {"yield_curve": {"crisis_signal": -1.0, "late_cycle_signal": 0.0}}},
    )
    assert result.regime == "late_cycle"
    assert "late_cycle" in result.votes


@pytest.mark.unit
def test_classify_credit_spread_crisis_dominates() -> None:
    """crisis vote 가 mid_cycle vote 보다 severity 우선."""
    result = classify_regime(
        {
            "yield_curve": _ind(1.0),                 # mid_cycle
            "credit_spread": _ind(9.0),               # crisis
        },
        {
            "thresholds": {
                "yield_curve": {"late_cycle_signal": 0.0, "crisis_signal": -1.0},
                "credit_spread": {"mid_cycle_max": 4.0, "late_cycle_min": 5.0, "crisis_min": 8.0},
            }
        },
    )
    assert result.regime == "crisis"
    assert set(result.votes) == {"mid_cycle", "crisis"}


@pytest.mark.unit
def test_classify_vix_uses_percentile_field() -> None:
    """vix indicator 는 value 가 아니라 percentile 로 vote."""
    ind = _ind(20.0, percentile=0.92)  # value 는 raw close, percentile 이 90+
    result = classify_regime(
        {"vix": ind},
        {"thresholds": {"vix": {"panic_min": 0.85, "complacent_max": 0.2}}},
    )
    assert "crisis" in result.votes


@pytest.mark.unit
def test_classify_breadth_healthy() -> None:
    result = classify_regime(
        {"breadth": _ind(0.7)},
        {"thresholds": {"breadth": {"healthy_min": 0.6, "late_cycle_max": 0.4, "crisis_max": 0.2}}},
    )
    assert result.regime == "mid_cycle"


# ----------------------------------------------------------------------
# main — envelope parity
# ----------------------------------------------------------------------


@pytest.mark.unit
def test_main_dry_run_produces_legacy_compatible_envelope(tmp_path: Path) -> None:
    """`--dry-run` 실행 → 00-macro-regime.json envelope 키 검증.

    legacy ``risk_engine.macro_regime`` 와 동일 schema:
    - schema / generated_at / date / config_path / config_version
    - regime_decision / cash_band / total_exposure_budget / indicators /
      regime_shift / warnings
    """
    exit_code = main(["--dry-run", "--trail-dir", str(tmp_path), "--date", "2026-05-17"])
    assert exit_code == 0

    out_path = tmp_path / "00-macro-regime.json"
    assert out_path.exists()
    envelope = json.loads(out_path.read_text(encoding="utf-8"))

    expected = {
        "schema",
        "generated_at",
        "date",
        "config_path",
        "config_version",
        "regime_decision",
        "cash_band",
        "total_exposure_budget",
        "indicators",
        "regime_shift",
        "warnings",
    }
    assert expected.issubset(envelope.keys())
    assert envelope["schema"] == SCHEMA_VERSION
    assert envelope["date"] == "2026-05-17"
    assert envelope["config_path"].endswith("regimes.yaml")

    # dry-run → 모든 indicator skip → regime=unknown
    rd = envelope["regime_decision"]
    assert rd["regime"] == "unknown"
    assert rd["votes"] == []

    # indicators key 4개 보존
    assert set(envelope["indicators"].keys()) == {"yield_curve", "credit_spread", "vix", "breadth"}

    # cash_band 는 unknown default [0.30, 0.70]
    assert envelope["cash_band"] == [0.30, 0.70]
    assert envelope["total_exposure_budget"] == 0.3


@pytest.mark.unit
def test_main_emits_handoff_summary(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    main(["--dry-run", "--trail-dir", str(tmp_path), "--date", "2026-05-17"])
    captured = capsys.readouterr()
    assert "[stage0-macro-regime]" in captured.out
    assert "date=2026-05-17" in captured.out
    assert "regime=unknown" in captured.out
    assert "00-macro-regime.json" in captured.out


@pytest.mark.unit
def test_indicator_skip_serializes_without_optional_fields(tmp_path: Path) -> None:
    """legacy 호환: percentile=None / skip_reason=None 은 envelope.indicators[name] 에서 누락."""
    main(["--dry-run", "--trail-dir", str(tmp_path), "--date", "2026-05-17"])
    envelope = json.loads((tmp_path / "00-macro-regime.json").read_text(encoding="utf-8"))
    # dry-run 시 모든 indicator 는 skip_reason="--dry-run" 보유 → 직렬화에 포함
    for ind in envelope["indicators"].values():
        assert "skip_reason" in ind  # dry-run 의 경우 skip_reason 보존
