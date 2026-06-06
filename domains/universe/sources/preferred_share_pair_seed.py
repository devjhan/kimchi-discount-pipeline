"""PreferredShareSeedSource — 우선주 페어 universe entry 발견.

원래 ``domains/alpha_factory/stage1_pref_spread.py:383-440`` 의 main() 이 직접
manual_pairs + auto-discover 호출하던 부분을 Source plugin 으로 분리.

각 (common, preferred) 페어를 *common ticker* 의 ``UniverseEntry`` 로 emit
(``source_category="preferred_share_pair"``). metadata 에 페어 상세 보존 —
``SpreadZScoreEnricher`` 가 본 metadata 를 읽어 z-score 계산.

config (sources.yaml entry):
    - type: "preferred_share_pair_seed"
      name: "preferred_share_pair"
      pairs_ref: "preferred_pairs.yaml"
      auto_discover: false           # true 시 DART KRX listing 기반 자동 발견 시도
      source_category: "preferred_share_pair"
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from domains.universe import _boundary
from domains.universe.domain.entry import UniverseEntry
from domains.universe.sources.base import DiscoveryContext, DiscoverySource, SourceResult
from domains.universe.sources.registry import register_source


@register_source("preferred_share_pair_seed")
@dataclass(frozen=True)
class PreferredShareSeedSource(DiscoverySource):
    """우선주/보통주 페어 → UniverseEntry seed (enricher 의 입력)."""

    name: str
    pairs: tuple[Mapping[str, Any], ...]
    auto_discover: bool = False
    source_category: str = "preferred_share_pair"

    @classmethod
    def from_spec(cls, spec: dict[str, Any]) -> "PreferredShareSeedSource":
        pairs = spec.get("pairs")
        if pairs is None:
            ref = spec.get("pairs_ref")
            if not ref:
                raise ValueError(
                    f"preferred_share_pair_seed '{spec.get('name')}': "
                    "pairs / pairs_ref 둘 다 부재"
                )
            loaded = _boundary.load_sub_config(ref)
            pairs = loaded.get("manual_pairs") or loaded.get("pairs") or []
        if not isinstance(pairs, list):
            raise ValueError(
                f"preferred_share_pair_seed '{spec.get('name')}': pairs 는 list 이어야 함"
            )
        return cls(
            name=spec["name"],
            pairs=tuple(pairs),
            auto_discover=bool(spec.get("auto_discover", False)),
            source_category=spec.get("source_category", "preferred_share_pair"),
        )

    def discover(self, ctx: DiscoveryContext) -> SourceResult:
        warnings: list[str] = []
        fetched_at = _boundary.now_iso_kst()
        env = dict(ctx.env)

        all_pairs = list(self.pairs)

        if self.auto_discover:
            if not _boundary.dart_has_key(env):
                warnings.append(
                    f"{self.name}: DART_API_KEY missing → auto_discover skipped"
                )
            else:
                try:
                    auto, auto_warns = _boundary.dart_discover_preferred_pairs(env)
                    warnings.extend(auto_warns)
                    merged, merge_warns = _boundary.dart_merge_preferred_pairs(
                        auto, list(self.pairs)
                    )
                    warnings.extend(merge_warns)
                    all_pairs = merged
                except (_boundary.DartUnavailable, Exception) as exc:  # noqa: BLE001
                    warnings.append(
                        f"{self.name}: auto_discover skipped — {type(exc).__name__}: {exc}"
                    )

        entries: list[UniverseEntry] = []
        seen: set[str] = set()
        for p in all_pairs:
            common = str(p.get("common") or "").strip()
            preferred = str(p.get("preferred") or "").strip()
            if not common or not preferred:
                warnings.append(f"{self.name}: invalid pair skipped — {p}")
                continue
            name_common = str(p.get("name_common") or common)
            name_preferred = str(p.get("name_preferred") or preferred)
            market = str(p.get("market") or "KOSPI")
            # dedup key 는 (common, preferred) pair — 같은 보통주에 우선주 종류가
            # 여럿 (예: 1우 / 2우) 일 때 모두 emit (외부 감사 fix 2026-05-17).
            dedup_key = f"{common}|{preferred}"
            if dedup_key in seen:
                continue
            seen.add(dedup_key)
            ticker = f"KR:{common}"
            entries.append(
                UniverseEntry(
                    ticker=ticker,
                    name=name_common,
                    source_category=self.source_category,
                    inclusion_reason=f"preferred share pair ({name_preferred})",
                    fetched_at=fetched_at,
                    source_citation=_boundary.format_citation(
                        "user", fetched_at, f"{self.name}/{common}-{preferred}"
                    ),
                    metadata={
                        "common": common,
                        "preferred": preferred,
                        "name_common": name_common,
                        "name_preferred": name_preferred,
                        "market": market,
                    },
                )
            )

        return SourceResult(
            entries=tuple(entries),
            warnings=tuple(warnings),
            degraded=False,
        )
