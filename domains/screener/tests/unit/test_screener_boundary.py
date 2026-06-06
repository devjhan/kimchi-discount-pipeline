"""screener _boundary 어댑터 factory 테스트.

citation_adapter() 가 CitationPort 를 만족 + format_citation free fn 과 byte-parity
(동일 ``_utils.format_citation`` 위임 — Phase 0 주입 전환이 행동을 바꾸지 않음을 보증).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from domains.screener import _boundary
from domains._shared.ports.citation import CitationPort


@pytest.mark.unit
def test_citation_adapter_satisfies_port() -> None:
    """citation_adapter() 반환이 CitationPort 를 만족."""
    assert isinstance(_boundary.citation_adapter(), CitationPort)


@pytest.mark.unit
def test_citation_adapter_byte_parity_with_free_fn() -> None:
    """adapter.format == _boundary.format_citation (동일 util 위임 — 행동 무변경)."""
    adapter = _boundary.citation_adapter()
    cases: list[tuple[str, str, object]] = [
        ("DART", "2026-05-15T15:30:00+09:00", {"corp": "00112378", "n": 3}),
        ("FRED", "2026-01-02T00:00:00+09:00", 4.21),
        ("KIS", "2026-05-15T09:00:00+09:00", "005930"),
    ]
    for source, ts, value in cases:
        assert adapter.format(source, ts, value) == _boundary.format_citation(
            source, ts, value
        )


@pytest.mark.unit
def test_resolve_path_dart_cache() -> None:
    """dart_cache alias → .cache/dart (corp_index 캐시 홈, universe 와 동형)."""
    p = _boundary.resolve_path("dart_cache")
    assert p.parts[-2:] == (".cache", "dart")


@pytest.mark.unit
def test_dart_load_corp_index_forwards_cache_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """B-1 회귀 가드: dart_load_corp_index 가 cache_path 를 infrastructure 로 전달.

    구 버그는 ``load_or_fetch_corp_code_index(api_key)`` 로 호출해 required
    positional ``cache_path`` 누락 → TypeError. 본 테스트는 cache_path 가 반드시
    forward 됨을 보장한다 (universe._boundary 와 동형).
    """
    seen: dict[str, object] = {}

    def _spy(api_key: str, cache_path: object) -> dict[str, str]:
        seen["api_key"] = api_key
        seen["cache_path"] = cache_path
        return {"005930": "00126380"}

    monkeypatch.setattr(_boundary._dart, "load_or_fetch_corp_code_index", _spy)
    cache = Path("/tmp/corp_index.json")
    result = _boundary.dart_load_corp_index("KEY", cache)
    assert seen == {"api_key": "KEY", "cache_path": cache}
    assert result == {"005930": "00126380"}
