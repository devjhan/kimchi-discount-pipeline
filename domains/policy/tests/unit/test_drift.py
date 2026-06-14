"""drift.py 직접 단위테스트 — compute_drift + _collect_thresholds.

이전엔 _shared/profile_registry/diff.py 였고 test_commit.py 가 간접 커버만 했다.
policy/domain 으로 이전(F-3)하며 도메인 룰로 승격 — 직접 단위테스트로 회귀 안전망 확보.
"""
from __future__ import annotations

import pytest

from domains.policy.domain.drift import _collect_thresholds, compute_drift
from domains._shared.profile_registry.schema import (
    SCHEMA_VERSION,
    EnrichCutoffProfile,
    Provenance,
)


def _profile(
    *,
    required: tuple[str, ...] = ("nav_discount",),
    threshold: float = 0.10,
) -> EnrichCutoffProfile:
    return EnrichCutoffProfile(
        ticker="KR:005930",
        schema_version=SCHEMA_VERSION,
        profile_version=1,
        required_enrichments=required,
        cutoff_rules={
            "type": "threshold",
            "name": "nav_floor",
            "metric_path": "enrichments.nav_discount.discount_pct",
            "op": "ge",
            "threshold": threshold,
        },
        provenance=Provenance(
            committed_at="2026-06-02T16:00:00+09:00",
            committed_by="policy",
            trigger="manual",
        ),
    )


@pytest.mark.unit
def test_initial_commit_zero_drift() -> None:
    drift = compute_drift(None, ("nav_discount",), {"type": "and", "children": []})
    assert drift.enrichments_added == ()
    assert drift.enrichments_removed == ()
    assert drift.changed_thresholds == {}
    assert drift.max_threshold_delta == 0.0


@pytest.mark.unit
def test_threshold_change_computes_relative_delta() -> None:
    prev = _profile(threshold=0.10)
    drift = compute_drift(
        prev,
        prev.required_enrichments,
        {**prev.cutoff_rules, "threshold": 0.30},
    )
    # |0.30 - 0.10| / |0.10| = 2.0
    assert drift.max_threshold_delta == pytest.approx(2.0)
    assert drift.changed_thresholds == {"nav_floor": (0.10, 0.30)}


@pytest.mark.unit
def test_enrichments_added_and_removed() -> None:
    prev = _profile(required=("nav_discount", "buyback"))
    drift = compute_drift(
        prev,
        ("nav_discount", "insider_cluster"),
        prev.cutoff_rules,
    )
    assert drift.enrichments_added == ("insider_cluster",)
    assert drift.enrichments_removed == ("buyback",)


@pytest.mark.unit
def test_zero_old_threshold_does_not_divide() -> None:
    prev = _profile(threshold=0.0)
    drift = compute_drift(prev, prev.required_enrichments, {**prev.cutoff_rules, "threshold": 0.5})
    # old == 0 → relative delta 계산 skip (ZeroDivision 회피), 변화 자체는 기록.
    assert drift.changed_thresholds == {"nav_floor": (0.0, 0.5)}
    assert drift.max_threshold_delta == 0.0


@pytest.mark.unit
def test_collect_thresholds_walks_children_and_inner() -> None:
    spec = {
        "type": "and",
        "children": [
            {"type": "threshold", "name": "a", "threshold": 1.0},
            {
                "type": "or",
                "inner": {"type": "threshold", "name": "b", "threshold": 2.0},
            },
        ],
    }
    assert _collect_thresholds(spec) == {"a": 1.0, "b": 2.0}


@pytest.mark.unit
def test_collect_thresholds_unwraps_weighted_sum() -> None:
    # weighted_sum children: {"rule": {...}, "weight": ...} 래핑 처리.
    spec = {
        "type": "weighted_sum",
        "children": [
            {"rule": {"type": "threshold", "name": "roic", "threshold": 0.08}, "weight": 0.6},
            {"rule": {"type": "threshold", "name": "fcf", "threshold": 0.05}, "weight": 0.4},
        ],
    }
    assert _collect_thresholds(spec) == {"roic": 0.08, "fcf": 0.05}


@pytest.mark.unit
def test_collect_thresholds_ignores_bool_threshold() -> None:
    # bool 은 int 서브타입이나 threshold 로 취급하지 않음.
    spec = {"type": "threshold", "name": "flag", "threshold": True}
    assert _collect_thresholds(spec) == {}


@pytest.mark.unit
def test_collect_thresholds_tracks_scoring_and_weighted_sum_pass_score() -> None:
    """finding 7 — scoring/weighted_sum 의 pass_score 도 drift 추적 (사각지대 제거)."""
    spec = {
        "type": "weighted_sum",
        "name": "ws",
        "pass_score": 0.55,
        "children": [
            {"rule": {"type": "scoring", "name": "roic_score", "pass_score": 0.4}, "weight": 1.0},
        ],
    }
    assert _collect_thresholds(spec) == {"ws": 0.55, "roic_score": 0.4}


@pytest.mark.unit
def test_scoring_pass_score_change_detected_as_drift() -> None:
    prev = EnrichCutoffProfile(
        ticker="KR:005930",
        schema_version=SCHEMA_VERSION,
        profile_version=1,
        required_enrichments=("nav_discount",),
        cutoff_rules={"type": "scoring", "name": "s", "metric_path": "annuals_avg.roic", "pass_score": 0.50},
        provenance=Provenance(committed_at="t", committed_by="policy", trigger="manual"),
    )
    drift = compute_drift(
        prev, prev.required_enrichments, {**prev.cutoff_rules, "pass_score": 0.75}
    )
    assert drift.changed_thresholds == {"s": (0.50, 0.75)}
    assert drift.max_threshold_delta == pytest.approx(0.5)
