"""universe.sources — DiscoverySource ABC + registry + factory + 2 source 검증.

Run 2 scope:
- ``LiteralListSource`` — items / items_ref 양쪽 입력, str / dict entry, 잘못된 entry 처리
- ``HoldingCompanySource`` — subsidiaries_map / _ref 입력, DART_API_KEY 부재 시 graceful skip
- ``factory.build_source`` — type dispatch, 누락된 type / name / 미등록 type 거부
- ``registry.register_source`` — 중복 등록 차단
"""
from __future__ import annotations

from datetime import date

import pytest

from domains._shared.time.clock import AsOfClock
from domains.universe.domain.entry import UniverseEntry
from domains.universe.sources.base import (
    DiscoveryContext,
    DiscoverySource,
    SourceResult,
)
from domains.universe.sources.factory import build_source, build_sources
from domains.universe.sources.holding_company import HoldingCompanySource
from domains.universe.sources.literal_list import LiteralListSource
from domains.universe.sources.registry import SOURCE_TYPES, register_source


def _ctx(env: dict[str, str] | None = None) -> DiscoveryContext:
    return DiscoveryContext(
        clock=AsOfClock.at_market_close(date(2026, 5, 17)),
        env=env or {},
    )


# ----------------------------------------------------------------------
# LiteralListSource
# ----------------------------------------------------------------------


@pytest.mark.unit
def test_literal_list_from_spec_inline_items() -> None:
    src = LiteralListSource.from_spec(
        {
            "type": "literal_list",
            "name": "manual",
            "items": ["KR:003550", {"ticker": "KR:028260", "name": "삼성물산", "reason": "NAV 진입"}],
        }
    )
    assert src.name == "manual"
    assert src.source_category == "manual_addition"
    assert len(src.items) == 2


@pytest.mark.unit
def test_literal_list_from_spec_missing_items_and_ref_rejected() -> None:
    with pytest.raises(ValueError, match="items / items_ref"):
        LiteralListSource.from_spec({"type": "literal_list", "name": "manual"})


@pytest.mark.unit
def test_literal_list_discover_str_and_dict_entries() -> None:
    src = LiteralListSource(
        name="manual",
        items=("KR:003550", {"ticker": "KR:028260", "name": "삼성물산", "reason": "test"}),
    )
    result = src.discover(_ctx())
    assert isinstance(result, SourceResult)
    assert len(result.entries) == 2
    tickers = [e.ticker for e in result.entries]
    assert tickers == ["KR:003550", "KR:028260"]
    # str entry → reason=default
    str_entry = result.entries[0]
    assert str_entry.inclusion_reason == "user_manual_addition"
    assert str_entry.source_category == "manual_addition"
    # dict entry → reason=custom
    dict_entry = result.entries[1]
    assert dict_entry.name == "삼성물산"
    assert dict_entry.inclusion_reason == "test"
    # G7 citation 형식 확인
    assert "user@" in str_entry.source_citation
    assert "=manual" in str_entry.source_citation
    assert result.degraded is False


@pytest.mark.unit
def test_literal_list_discover_skips_invalid_entries() -> None:
    src = LiteralListSource(
        name="manual",
        items=(
            123,  # invalid type
            "",  # empty string
            {"ticker": "", "name": "x"},  # empty ticker in dict
            "KR:003550",  # valid
        ),
    )
    result = src.discover(_ctx())
    assert len(result.entries) == 1
    assert result.entries[0].ticker == "KR:003550"
    # 3 invalid entries → 3 warnings
    assert len(result.warnings) == 3


@pytest.mark.unit
def test_literal_list_returns_immutable_entry() -> None:
    src = LiteralListSource(name="manual", items=("KR:003550",))
    result = src.discover(_ctx())
    assert isinstance(result.entries[0], UniverseEntry)
    assert isinstance(result.entries, tuple)
    assert isinstance(result.warnings, tuple)


# ----------------------------------------------------------------------
# HoldingCompanySource
# ----------------------------------------------------------------------


@pytest.mark.unit
def test_holding_company_from_spec_inline_map() -> None:
    src = HoldingCompanySource.from_spec(
        {
            "type": "holding_company",
            "name": "hold",
            "subsidiaries_map": {
                "KR:003550": [
                    {"stock_code": "051910", "name": "LG화학", "ownership_pct": 0.305, "listed": True}
                ],
            },
        }
    )
    assert src.name == "hold"
    assert src.source_category == "holding_company"
    assert "KR:003550" in src.subsidiaries_map


@pytest.mark.unit
def test_holding_company_from_spec_missing_map_and_ref_rejected() -> None:
    with pytest.raises(ValueError, match="subsidiaries_map"):
        HoldingCompanySource.from_spec({"type": "holding_company", "name": "hold"})


@pytest.mark.unit
def test_holding_company_emits_parent_entries_without_dart_key() -> None:
    """외부 감사 fix 2026-05-17: subsidiaries.yaml 만으로도 parent entries emit.

    이전 동작: DART_API_KEY 없으면 entries=() — NavDiscountEnricher 가 dead code.
    수정 후: entries 는 subsidiaries.yaml 만 의존 → DART skip 시에도 emit, audit
    log 만 best-effort skip.
    """
    src = HoldingCompanySource(
        name="hold",
        subsidiaries_map={
            "KR:003550": [{"stock_code": "051910", "name": "LG화학", "ownership_pct": 0.305, "listed": True}],
        },
    )
    result = src.discover(_ctx(env={}))
    assert len(result.entries) == 1
    e = result.entries[0]
    assert e.ticker == "KR:003550"
    assert e.source_category == "holding_company"
    assert e.metadata["n_subsidiaries"] == 1
    # G7 citation 형식
    assert "user@" in e.source_citation
    assert "subsidiaries.yaml" in e.source_citation
    # DART skip warning 보존 (entries 는 정상이지만 audit 미수행 가시화)
    assert any("DART_API_KEY missing" in w and "audit skipped" in w for w in result.warnings)
    assert result.degraded is False


@pytest.mark.unit
def test_holding_company_empty_map_returns_empty_with_warning() -> None:
    """subsidiaries_map 자체가 비어있으면 entries=() (할 게 없음)."""
    src = HoldingCompanySource(name="hold", subsidiaries_map={})
    result = src.discover(_ctx(env={"DART_API_KEY": "dummy"}))
    assert result.entries == ()
    assert any("subsidiaries_map 비어 있음" in w for w in result.warnings)


@pytest.mark.unit
def test_holding_company_emits_one_entry_per_parent() -> None:
    """subsidiaries_map 의 모든 parent ticker 마다 1 entry."""
    src = HoldingCompanySource(
        name="hold",
        subsidiaries_map={
            "KR:003550": [{"stock_code": "051910"}],
            "KR:034730": [{"stock_code": "017670"}, {"stock_code": "012630"}],
        },
    )
    result = src.discover(_ctx(env={}))
    assert len(result.entries) == 2
    tickers = sorted(e.ticker for e in result.entries)
    assert tickers == ["KR:003550", "KR:034730"]
    # metadata.n_subsidiaries 정합
    by_ticker = {e.ticker: e for e in result.entries}
    assert by_ticker["KR:003550"].metadata["n_subsidiaries"] == 1
    assert by_ticker["KR:034730"].metadata["n_subsidiaries"] == 2


@pytest.mark.unit
def test_holding_company_normalizes_ticker_prefix() -> None:
    """parent key 가 'KR:' prefix 없으면 자동 추가."""
    src = HoldingCompanySource(
        name="hold",
        subsidiaries_map={"003550": [{"stock_code": "051910"}]},
    )
    result = src.discover(_ctx(env={}))
    assert result.entries[0].ticker == "KR:003550"


# ----------------------------------------------------------------------
# PreferredShareSeedSource (Run 5) — 외부 감사 fix 2026-05-17 (dedup key)
# ----------------------------------------------------------------------


@pytest.mark.unit
def test_preferred_seed_dedup_by_pair_not_common_only() -> None:
    """같은 보통주에 우선주 종류가 여럿 (1우 / 2우) 일 때 둘 다 emit.

    이전 dedup key 가 ticker(common) 만이라 두 번째 페어가 silently 누락됐음.
    fix: dedup key=f'{common}|{preferred}'.
    """
    from domains.universe.sources.preferred_share_pair_seed import PreferredShareSeedSource

    src = PreferredShareSeedSource(
        name="pref",
        pairs=(
            {"common": "005930", "preferred": "005935", "market": "KOSPI"},
            {"common": "005930", "preferred": "005937", "market": "KOSPI"},  # 다른 우선주
            {"common": "005930", "preferred": "005935", "market": "KOSPI"},  # exact dup
        ),
    )
    result = src.discover(_ctx())
    # 2 entries — 두 다른 우선주 페어, exact dup 1개 drop
    assert len(result.entries) == 2
    pref_tickers = [e.metadata["preferred"] for e in result.entries]
    assert set(pref_tickers) == {"005935", "005937"}


# ----------------------------------------------------------------------
# Factory + Registry
# ----------------------------------------------------------------------


@pytest.mark.unit
def test_factory_builds_literal_list_via_dispatch() -> None:
    spec = {
        "type": "literal_list",
        "name": "m",
        "items": ["KR:003550"],
    }
    src = build_source(spec)
    assert isinstance(src, LiteralListSource)


@pytest.mark.unit
def test_factory_builds_holding_company_via_dispatch() -> None:
    spec = {
        "type": "holding_company",
        "name": "h",
        "subsidiaries_map": {},
    }
    src = build_source(spec)
    assert isinstance(src, HoldingCompanySource)


@pytest.mark.unit
def test_factory_rejects_missing_type() -> None:
    with pytest.raises(ValueError, match="missing 'type'"):
        build_source({"name": "x"})


@pytest.mark.unit
def test_factory_rejects_missing_name() -> None:
    with pytest.raises(ValueError, match="missing 'name'"):
        build_source({"type": "literal_list"})


@pytest.mark.unit
def test_factory_rejects_unknown_type() -> None:
    with pytest.raises(ValueError, match="unknown source type"):
        build_source({"type": "nonexistent_xyz", "name": "x"})


@pytest.mark.unit
def test_factory_rejects_non_dict_spec() -> None:
    with pytest.raises(ValueError, match="dict"):
        build_source(["not", "a", "dict"])  # type: ignore[arg-type]


@pytest.mark.unit
def test_registry_rejects_duplicate_registration() -> None:
    # SOURCE_TYPES 에 이미 등록된 이름으로 재시도
    with pytest.raises(ValueError, match="already registered"):

        @register_source("literal_list")  # 이미 등록됨
        class Dupe(DiscoverySource):  # type: ignore[misc]
            name: str = "x"
            source_category: str = "x"

            @classmethod
            def from_spec(cls, spec):  # type: ignore[no-untyped-def]
                return cls()

            def discover(self, ctx):  # type: ignore[no-untyped-def]
                return SourceResult((), ())


@pytest.mark.unit
def test_build_sources_aggregates_list() -> None:
    specs = [
        {"type": "literal_list", "name": "a", "items": []},
        {"type": "holding_company", "name": "b", "subsidiaries_map": {}},
    ]
    sources = build_sources(specs)
    assert len(sources) == 2
    assert isinstance(sources[0], LiteralListSource)
    assert isinstance(sources[1], HoldingCompanySource)


# ----------------------------------------------------------------------
# Real config file integration (sources.yaml / subsidiaries.yaml 로드 검증)
# ----------------------------------------------------------------------


@pytest.mark.unit
def test_sources_yaml_loadable_and_dispatches() -> None:
    """config/sources.yaml 이 실제 build_sources() 로 인스턴스화 가능."""
    from domains.universe import _boundary

    cfg = _boundary.load_sources_config()
    assert cfg["schema"] == "universe-sources-v1"
    sources = build_sources(cfg["sources"])
    types = {type(s).__name__ for s in sources}
    assert "LiteralListSource" in types
    assert "HoldingCompanySource" in types


@pytest.mark.unit
def test_sub_config_basename_only() -> None:
    """load_sub_config / config_path 는 path traversal 차단."""
    from domains.universe import _boundary

    with pytest.raises(ValueError, match="basename"):
        _boundary.load_sub_config("../etc/passwd")
    with pytest.raises(ValueError, match="basename"):
        _boundary.config_path("subdir/foo.yaml")


@pytest.mark.unit
def test_registered_source_types_includes_run2_set() -> None:
    """factory import 후 SOURCE_TYPES 에 Run 2 의 2 source 가 등록되어 있어야 함."""
    assert "literal_list" in SOURCE_TYPES
    assert "holding_company" in SOURCE_TYPES
