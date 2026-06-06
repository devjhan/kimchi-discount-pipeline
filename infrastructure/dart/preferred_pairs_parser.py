"""
infrastructure/dart/preferred_pairs_parser.py — 우선주/보통주 pair 자동 발견
(DART corpCode.xml 기반 본구현).

KRX 상장 우선주는 다음 명명규칙을 가진다 (대부분):
    - 회사명 suffix: "...우" / "...우B" / "...우C" / "...1우B" / ...
    - ticker suffix: 보통주 ticker 끝 자리 +5
      (예: 005930 삼성전자 ↔ 005935 삼성전자우,
           005380 현대차   ↔ 005385 현대차우,
           051910 LG화학   ↔ 051915 LG화학우)

본 parser 는 corpCode.xml 의 모든 listed 회사를 scan 해 위 두 조건을 동시
만족하는 pair 를 자동 발견한다. 정확도 검증을 위한 추가 ticker fetch 는
하지 않으며 (G6/G8 정합), manual_pairs SSOT (thresholds.yaml) 가 충돌 시
우선한다 (caller 가 merge).

설계 원칙 (plan D1 결정):
    manual SSOT 우선:
        governance/thresholds.yaml.universe.preferred_share_pairs.manual_pairs
        가 single source. 본 parser 결과는 보조.

Hard guards:
    G6: ticker 매칭은 deterministic 규칙
    G8: DART_API_KEY 누락 시 graceful skip (raise 금지)
"""

from __future__ import annotations

from typing import Any

from infrastructure.dart.client import (
    DartUnavailable,
    load_or_fetch_corp_full_index,
)
from infrastructure._common.utils import repo_path as _repo_path

# 우선주 회사명 suffix (긴 것부터 매칭 — 우선순위 important)
_PREFERRED_NAME_SUFFIXES = ("1우B", "2우B", "3우B", "우B", "우C", "우")


def _strip_preferred_suffix(name: str) -> tuple[str, str | None]:
    """우선주 회사명 → (보통주 회사명, suffix). 매칭 실패 시 (name, None)."""
    n = name.strip()
    for sfx in _PREFERRED_NAME_SUFFIXES:
        if n.endswith(sfx):
            base = n[: -len(sfx)].rstrip()
            if base:
                return base, sfx
    return n, None


def _preferred_to_common_ticker(preferred_ticker: str) -> str | None:
    """우선주 ticker → 보통주 ticker 후보. KRX 명명규칙 (끝자리 5 → 0).

    Returns:
        6자리 보통주 ticker 또는 None (매칭 패턴 위반 시).
    """
    if not preferred_ticker or len(preferred_ticker) != 6 or not preferred_ticker.isdigit():
        return None
    if preferred_ticker[-1] != "5":
        return None
    return preferred_ticker[:-1] + "0"


def discover_pairs_from_corp_index(
    corp_full_index: list[dict[str, str]],
) -> tuple[list[dict[str, Any]], list[str]]:
    """
    corp_full_index → 우선주/보통주 pair list.

    매칭 룰 (양쪽 모두 성립해야 함, AND):
        - 이름: preferred name strip suffix == common name
        - ticker: preferred ticker[-1]=='5', common ticker = preferred[:-1]+'0'

    Args:
        corp_full_index: DART load_or_fetch_corp_full_index() 결과.

    Returns:
        pairs: [
            {
                "common": "005930",
                "preferred": "005935",
                "name_common": "삼성전자",
                "name_preferred": "삼성전자우",
                "preferred_suffix": "우",
                "market": "unknown",   # corpCode.xml 에는 KOSPI/KOSDAQ 구분 없음
                "confidence": "auto_parsed_high",
                "source_citation": "DART@corpCode=...",
            },
        ]
        warnings: list[str]
    """
    warnings: list[str] = []
    by_stock: dict[str, dict[str, str]] = {}
    by_name: dict[str, str] = {}  # name → stock_code (단 첫 매치만)

    for entry in corp_full_index:
        stock = (entry.get("stock_code") or "").strip()
        name = (entry.get("corp_name") or "").strip()
        if not stock or not name:
            continue
        by_stock[stock] = {"name": name}
        by_name.setdefault(name, stock)

    pairs: list[dict[str, Any]] = []
    seen_preferred: set[str] = set()
    for stock, info in by_stock.items():
        name = info["name"]
        base_name, suffix = _strip_preferred_suffix(name)
        if suffix is None:
            continue  # 보통주 / 우선주 아님
        common_ticker = _preferred_to_common_ticker(stock)
        if not common_ticker:
            warnings.append(
                f"preferred-name detected but ticker pattern fail: "
                f"name='{name}', ticker='{stock}'"
            )
            continue
        common_info = by_stock.get(common_ticker)
        if common_info is None:
            warnings.append(
                f"preferred '{name}'({stock}) → common ticker {common_ticker} "
                "not in corp index (델리스팅 or unlisted)"
            )
            continue
        if _strip_preferred_suffix(common_info["name"])[1] is not None:
            # common candidate 도 "...우" suffix → 매칭 실패 (예외 케이스)
            warnings.append(
                f"both '{name}' and '{common_info['name']}' look preferred — skip"
            )
            continue
        if common_info["name"].rstrip() != base_name:
            # 이름 매칭 실패 (가끔 corpCode 데이터에 미세한 차이)
            # base_name in common_name 까지 허용 (partial)
            if base_name not in common_info["name"]:
                warnings.append(
                    f"name mismatch: preferred='{name}' base='{base_name}' "
                    f"vs common='{common_info['name']}' — skip"
                )
                continue

        if stock in seen_preferred:
            continue
        seen_preferred.add(stock)

        pairs.append(
            {
                "common": common_ticker,
                "preferred": stock,
                "name_common": common_info["name"],
                "name_preferred": name,
                "preferred_suffix": suffix,
                "market": "unknown",  # corpCode.xml 미제공
                "confidence": "auto_parsed_high",
                "source_citation": f"DART@corpCode={stock}",
            }
        )
    # deterministic order — by preferred ticker
    pairs.sort(key=lambda p: p["preferred"])
    return pairs, warnings


def discover_pairs_from_listing(env: dict[str, str]) -> tuple[list[dict[str, Any]], list[str]]:
    """
    Top-level entry — env 에서 DART_API_KEY load → corp_full_index fetch
    → discover_pairs_from_corp_index().

    Cache: .cache/dart/corp_full_index.json (7일 TTL).

    Returns:
        (pairs, warnings) — DART_API_KEY 누락 / fetch 실패 시 ([], warnings).
    """
    warnings: list[str] = []
    api_key = (env or {}).get("DART_API_KEY", "").strip()
    if not api_key:
        warnings.append(
            "DART_API_KEY missing → preferred_pair auto-discovery skip "
            "(manual_pairs SSOT 사용)"
        )
        return [], warnings

    cache_path = _repo_path(".cache", "dart") / "corp_full_index.json"
    try:
        corp_full_index = load_or_fetch_corp_full_index(api_key, cache_path)
    except DartUnavailable as exc:
        warnings.append(f"corpCode.xml fetch fail: {exc}")
        return [], warnings

    pairs, parse_warnings = discover_pairs_from_corp_index(corp_full_index)
    warnings.extend(parse_warnings[:5])  # cap — corpCode 의 일부 corner case 가 자주 발생
    if len(parse_warnings) > 5:
        warnings.append(f"... {len(parse_warnings) - 5} more parse warnings suppressed")
    return pairs, warnings


def merge_with_manual_pairs(
    auto_pairs: list[dict[str, Any]],
    manual_pairs: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    """
    Manual SSOT 우선 merge — plan D1 정합.

    Rules:
        1. manual_pairs 의 모든 entry 는 그대로 유지. confidence='manual_ssot'
           + market 필드는 manual 값 (KOSPI/KOSDAQ) 보존.
        2. auto_pairs 중 manual_pairs 의 preferred ticker 와 일치하지 않는 entry
           만 추가.

    Returns:
        (merged, warnings)
    """
    warnings: list[str] = []
    manual_preferred = {
        str(p.get("preferred", "")).strip()
        for p in manual_pairs
        if p.get("preferred")
    }
    out: list[dict[str, Any]] = []
    for p in manual_pairs:
        new = dict(p)
        new.setdefault("confidence", "manual_ssot")
        out.append(new)
    for p in auto_pairs:
        pref = str(p.get("preferred") or "").strip()
        if not pref or pref in manual_preferred:
            continue
        out.append(p)
    return out, warnings


__all__ = [
    "discover_pairs_from_corp_index",
    "discover_pairs_from_listing",
    "merge_with_manual_pairs",
    "_strip_preferred_suffix",
    "_preferred_to_common_ticker",
]
