"""main.py 의 _collect_profile_refs nested 수집 검증.

CRITICAL 결함 cover — 기존 main.py 가 top-level profile_ref 만 지원해
AND/OR 합성 strategy 가 빌드 실패하던 문제 회귀 방지.
"""
from __future__ import annotations

import pytest

from domains.screener.main import _collect_profile_refs


@pytest.mark.unit
def test_collect_profile_refs_top_level() -> None:
    spec = {"type": "profile_ref", "profile": "quality_floor"}
    assert _collect_profile_refs(spec) == {"quality_floor"}


@pytest.mark.unit
def test_collect_profile_refs_nested_and() -> None:
    spec = {
        "type": "and",
        "children": [
            {"type": "profile_ref", "profile": "quality_floor"},
            {"type": "profile_ref", "profile": "low_psr"},
        ],
    }
    assert _collect_profile_refs(spec) == {"quality_floor", "low_psr"}


@pytest.mark.unit
def test_collect_profile_refs_nested_weighted_sum() -> None:
    spec = {
        "type": "weighted_sum",
        "pass_score": 0.4,
        "children": [
            {"rule": {"type": "profile_ref", "profile": "nav_discount"}, "weight": 0.7},
            {"rule": {"type": "profile_ref", "profile": "activist"}, "weight": 0.3},
        ],
    }
    assert _collect_profile_refs(spec) == {"nav_discount", "activist"}


@pytest.mark.unit
def test_collect_profile_refs_deeply_nested() -> None:
    spec = {
        "type": "and",
        "children": [
            {"type": "profile_ref", "profile": "quality_floor"},
            {
                "type": "or",
                "children": [
                    {"type": "profile_ref", "profile": "low_psr"},
                    {"type": "not", "inner": {"type": "profile_ref", "profile": "exclude"}},
                ],
            },
        ],
    }
    assert _collect_profile_refs(spec) == {"quality_floor", "low_psr", "exclude"}


@pytest.mark.unit
def test_collect_profile_refs_empty_when_no_profile() -> None:
    spec = {
        "type": "threshold",
        "name": "ic",
        "metric_path": "latest_annual.interest_coverage",
        "op": "ge",
        "threshold": 4.0,
    }
    assert _collect_profile_refs(spec) == set()


@pytest.mark.unit
def test_collect_profile_refs_handles_non_dict() -> None:
    assert _collect_profile_refs(None) == set()  # type: ignore[arg-type]
    assert _collect_profile_refs([]) == set()  # type: ignore[arg-type]
