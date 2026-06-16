"""HoldingCompanySource — 지주사 universe entry emit + DART subsidiaries audit.

원래 ``domains/alpha_factory/universe.py:74-199`` 의 ``discover_holding_companies``
를 Source plugin 패턴으로 이전. *Run 5 비대칭 제거* (2026-05-17 외부 감사 fix):
원래는 entries=() + audit log only 였으나, 그 결과 NavDiscountEnricher
(``applies_to={"holding_company"}``) 가 dead code 가 됨. fix: subsidiaries.yaml
의 parent ticker 마다 ``source_category="holding_company"`` entry 를 emit 해
enrichment chain 활성화.

흐름:
1. subsidiaries_map 비어있으면 entries=() + warning (할 게 없음)
2. parent ticker 마다 UniverseEntry 생성 (DART 의존 없음 — subsidiaries.yaml 만 필요)
3. DART_API_KEY 가 있으면 best-effort audit log 생성 (사업보고서 파싱 + manual SSoT merge)
   ``$AUDIT_DIR/subsidiaries/subsidiaries-audit-{date}.json``. audit 실패는 entries 에 영향 없음.

config:
    - type: "holding_company"
      name: "holding_company"
      subsidiaries_map_ref: "subsidiaries.yaml"

향후 확장: subsidiaries.yaml schema 에 ``parent_name`` 필드 추가하면 entry.name
이 ticker fallback 대신 회사명. 현재는 ticker key 자체 (예: "KR:003550") 를 name 으로.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from domains.universe import _boundary
from domains.universe.domain.entry import UniverseEntry
from domains.universe.sources.base import DiscoveryContext, DiscoverySource, SourceResult
from domains.universe.sources.registry import register_source

_AUDIT_ALIAS = "operations_audit"
_AUDIT_SCHEMA = "investment-subsidiaries-audit-v1"


@register_source("holding_company")
@dataclass(frozen=True)
class HoldingCompanySource(DiscoverySource):
    """지주사 parent ticker emit + DART subsidiaries audit (best-effort)."""

    name: str
    subsidiaries_map: Mapping[str, list[Mapping[str, Any]]]
    source_category: str = "holding_company"

    @classmethod
    def from_spec(cls, spec: dict[str, Any]) -> "HoldingCompanySource":
        smap = spec.get("subsidiaries_map")
        if smap is None:
            ref = spec.get("subsidiaries_map_ref")
            if not ref:
                raise ValueError(
                    f"holding_company source '{spec.get('name')}': "
                    "subsidiaries_map / subsidiaries_map_ref 둘 다 부재"
                )
            loaded = _boundary.load_sub_config(ref)
            smap = loaded.get("subsidiaries_map") or {}
        if not isinstance(smap, dict):
            raise ValueError(
                f"holding_company source '{spec.get('name')}': "
                "subsidiaries_map 은 dict 이어야 함"
            )
        return cls(
            name=spec["name"],
            subsidiaries_map=smap,
            source_category=spec.get("source_category", "holding_company"),
        )

    def discover(self, ctx: DiscoveryContext) -> SourceResult:
        warnings: list[str] = []
        env = dict(ctx.env)
        fetched_at = _boundary.now_iso_kst()
        date_str = ctx.clock.trading_date.isoformat()

        if not self.subsidiaries_map:
            warnings.append(
                f"{self.name}: subsidiaries_map 비어 있음 — entries 0건"
            )
            return SourceResult(entries=(), warnings=tuple(warnings), degraded=False)

        # ---- (1) parent ticker entries — DART 의존 없음, subsidiaries.yaml SSoT 직접 사용 ----
        entries: list[UniverseEntry] = []
        for parent_ticker_key, manual_entries in self.subsidiaries_map.items():
            ticker = (
                parent_ticker_key
                if parent_ticker_key.startswith("KR:")
                else f"KR:{parent_ticker_key.strip()}"
            )
            entries.append(
                UniverseEntry(
                    ticker=ticker,
                    name=parent_ticker_key,  # subsidiaries.yaml 에 parent_name 필드 없음 — ticker fallback
                    source_category=self.source_category,
                    inclusion_reason=(
                        f"holding company (subsidiaries.yaml, "
                        f"n_subsidiaries={len(manual_entries)})"
                    ),
                    fetched_at=fetched_at,
                    source_citation=_boundary.format_citation(
                        "user", fetched_at, f"subsidiaries.yaml/{parent_ticker_key}"
                    ),
                    metadata={
                        "n_subsidiaries": len(manual_entries),
                        "parent_ticker_key": parent_ticker_key,
                    },
                )
            )

        # ---- (2) DART audit log (best-effort side effect) ----
        # DART 미가용 / fetch 실패는 audit 만 skip — entries 는 살아있음
        if not _boundary.dart_has_key(env):
            warnings.append(
                f"{self.name}: DART_API_KEY missing → subsidiaries audit skipped "
                "(entries 는 정상 emit)"
            )
            return SourceResult(entries=tuple(entries), warnings=tuple(warnings), degraded=False)

        audit_dir = _boundary.resolve_path(_AUDIT_ALIAS)
        audit_dir.mkdir(parents=True, exist_ok=True)
        # DART corp index 는 재생성 가능 캐시 → .cache/dart (audit 증거와 분리)
        dart_cache_dir = _boundary.resolve_path("dart_cache")
        dart_cache_dir.mkdir(parents=True, exist_ok=True)
        # F-15: 디렉토리(.cache/)가 이미 숨김이라 파일 단위 leading-dot 제거.
        corp_index_path = dart_cache_dir / "corp_index.json"
        corp_full_index_path = dart_cache_dir / "corp_full_index.json"

        api_key = env.get("DART_API_KEY", "").strip()
        try:
            stock_to_corp = _boundary.dart_load_corp_index(api_key, corp_index_path)
            corp_full_index = _boundary.dart_load_corp_full_index(
                api_key, corp_full_index_path
            )
        except _boundary.DartUnavailable as exc:
            warnings.append(
                f"{self.name}: corpCode load fail → subsidiaries audit skipped: {exc}"
            )
            return SourceResult(entries=tuple(entries), warnings=tuple(warnings), degraded=False)

        # 전년도 사업보고서 (당해는 3월 발행 전 안 나옴)
        bsns_year = str(ctx.clock.trading_date.year - 1)
        audit_payload: dict[str, Any] = {
            "schema": _AUDIT_SCHEMA,
            "generated_at": fetched_at,
            "date": date_str,
            "bsns_year": bsns_year,
            "parents": [],
        }

        for parent_ticker_key, manual_entries in self.subsidiaries_map.items():
            stock = parent_ticker_key.replace("KR:", "").strip()
            corp = stock_to_corp.get(stock)
            if not corp:
                warnings.append(
                    f"{self.name}: parent {parent_ticker_key} corp_code 매핑 실패 "
                    "— corpCode.xml 갱신 필요"
                )
                continue
            auto_entries, parse_warnings = _boundary.dart_parse_subsidiary_table(
                corp,
                bsns_year=bsns_year,
                env=env,
                corp_full_index=corp_full_index,
            )
            warnings.extend(parse_warnings)
            merged, merge_warnings = _boundary.dart_merge_with_manual_ssot(
                auto_entries, list(manual_entries)
            )
            warnings.extend(merge_warnings)
            audit_payload["parents"].append(
                {
                    "parent_ticker": parent_ticker_key,
                    "parent_corp_code": corp,
                    "manual_count": len(manual_entries),
                    "auto_count": len(auto_entries),
                    "merged_count": len(merged),
                    "auto_only_additions": [
                        e for e in merged
                        if e.get("confidence", "").startswith("auto_parsed")
                    ],
                }
            )

        subsidiaries_dir = audit_dir / "subsidiaries"
        subsidiaries_dir.mkdir(parents=True, exist_ok=True)
        audit_path = subsidiaries_dir / f"subsidiaries-audit-{date_str}.json"
        _boundary.write_output_safely(audit_path, audit_payload)
        warnings.append(
            f"{self.name}: subsidiaries audit log {audit_path.name} "
            f"(parents={len(audit_payload['parents'])} — 검토 후 subsidiaries.yaml 갱신 권장)"
        )

        return SourceResult(entries=tuple(entries), warnings=tuple(warnings), degraded=False)
