"""NavDiscountEnricher — 지주사 NAV 할인 attribute attach.

원래 ``domains/alpha_factory/stage1_nav_calc.py`` 의 ``evaluate_holding_company``
+ ``compute_nav`` (L172-325) 를 Enricher plugin 패턴으로 이전.

``applies_to = {"holding_company"}`` — 다른 source_category 의 entry 는 pass-through.

attributes (EnrichedEntry.enrichments["nav_discount"]):
- ``parent_market_cap`` — float | None (KIS 시총)
- ``nav_estimate`` — float | None (Σ sub_market_cap × ownership_pct, indirect_via 제외)
- ``discount_pct`` — float | None (1 - parent_mcap / nav, 4자리 round)
- ``subsidiaries`` — list[dict] (각 자회사의 contribution 상세, debug 용)

citations: KIS@{ts}={stock_code, market_cap} 형식 (parent + 각 자회사)

config:
    - type: "nav_discount"
      name: "nav_discount"
      applies_to: ["holding_company"]
      subsidiaries_map_ref: "subsidiaries.yaml"
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from domains._shared import nav_history
from domains.universe import _boundary
from domains.universe.domain.enriched import EnrichmentResult
from domains.universe.domain.entry import UniverseEntry
from domains.universe.enrichers.base import EnrichContext, Enricher
from domains.universe.enrichers.registry import register_enricher


@register_enricher("nav_discount")
@dataclass(frozen=True)
class NavDiscountEnricher(Enricher):
    """지주사 NAV / discount 계산. KIS 시총 fetch → ownership_pct 가중합."""

    name: str
    subsidiaries_map: Mapping[str, list[Mapping[str, Any]]]
    applies_to: frozenset[str] = frozenset({"holding_company"})

    @classmethod
    def from_spec(cls, spec: dict[str, Any]) -> "NavDiscountEnricher":
        smap = spec.get("subsidiaries_map")
        if smap is None:
            ref = spec.get("subsidiaries_map_ref")
            if not ref:
                raise ValueError(
                    f"nav_discount enricher '{spec.get('name')}': "
                    "subsidiaries_map / subsidiaries_map_ref 둘 다 부재"
                )
            loaded = _boundary.load_sub_config(ref)
            smap = loaded.get("subsidiaries_map") or {}
        if not isinstance(smap, dict):
            raise ValueError(
                f"nav_discount enricher '{spec.get('name')}': "
                "subsidiaries_map 은 dict 이어야 함"
            )
        applies_to_raw = spec.get("applies_to") or ["holding_company"]
        return cls(
            name=spec["name"],
            subsidiaries_map=smap,
            applies_to=frozenset(str(c) for c in applies_to_raw),
        )

    def enrich(self, entry: UniverseEntry, ctx: EnrichContext) -> EnrichmentResult:
        sub_map_raw = self.subsidiaries_map.get(entry.ticker)
        if not sub_map_raw:
            return EnrichmentResult(
                attributes={},
                citations=(),
                warnings=(),
                skip_reason=f"subsidiaries.yaml 에 {entry.ticker} 매핑 부재",
            )

        env = dict(ctx.env)
        if not _boundary.kis_has_keys(env):
            return EnrichmentResult(
                attributes={},
                citations=(),
                warnings=(),
                skip_reason="KIS_APP_KEY/SECRET missing — 시총 fetch 불가",
            )

        fetched_at = _boundary.now_iso_kst()
        citations: list[str] = []
        warnings: list[str] = []

        # parent 시총
        parent_code = entry.ticker.split(":", 1)[1]
        parent_mcap, parent_err, parent_cite = _fetch_market_cap(
            env=env, stock_code=parent_code, fetched_at=fetched_at
        )
        if parent_cite:
            citations.append(parent_cite)
        if parent_err:
            warnings.append(f"{entry.ticker} parent: {parent_err}")

        # 자회사 처리
        sub_contribs: list[dict[str, Any]] = []
        for s in sub_map_raw:
            stock_code = str(s.get("stock_code") or "").strip()
            sub_name = str(s.get("name") or stock_code)
            ownership = float(s.get("ownership_pct") or 0.0)
            listed = bool(s.get("listed", True))
            indirect_via = s.get("indirect_via")

            if not stock_code or len(stock_code) != 6:
                sub_contribs.append(_skipped_contrib(s, sub_name, "invalid stock_code"))
                continue
            if not listed:
                sub_contribs.append(_skipped_contrib(s, sub_name, "non-listed (장부가 reference 미구현)"))
                continue
            if indirect_via:
                sub_contribs.append(_skipped_contrib(s, sub_name, f"indirect ownership via {indirect_via}"))
                continue

            sub_mcap, sub_err, sub_cite = _fetch_market_cap(
                env=env, stock_code=stock_code, fetched_at=fetched_at
            )
            if sub_cite:
                citations.append(sub_cite)
            if sub_err:
                warnings.append(f"{entry.ticker} sub {stock_code}: {sub_err}")
            contribution = (
                round(sub_mcap * ownership, 2) if sub_mcap is not None else None
            )
            sub_contribs.append(
                {
                    "name": sub_name,
                    "stock_code": stock_code,
                    "ownership_pct": ownership,
                    "listed": listed,
                    "indirect_via": indirect_via,
                    "sub_market_cap": sub_mcap,
                    "contribution": contribution,
                    "citation": sub_cite,
                    "skip_reason": sub_err,
                }
            )

        nav, discount = _compute_nav(parent_mcap=parent_mcap, sub_contribs=sub_contribs)

        # nav-history snapshot append (cross-day 증거 → catalyst nav_discount_narrowing
        # detector 가 소비, B-2). discount is not None ⟹ parent_mcap & nav>0 둘 다 유효
        # (premium 의미 있음). build_universe 는 dry_run 시 enrich() 자체를 호출하지 않으므로
        # 별도 dry-run 가드 불요. 같은 거래일 재실행 중복은 멱등 사전체크로 방지.
        if discount is not None and parent_mcap and nav:
            snap_date = ctx.clock.trading_date.isoformat()
            already = any(
                r.get("date") == snap_date
                for r in nav_history.load_nav_history(entry.ticker)
            )
            if not already:
                nav_history.append_nav_snapshot(
                    entry.ticker,
                    snap_date,
                    parent_mcap_krw=parent_mcap,
                    nav_sum_krw=nav,
                    premium_pct=round(parent_mcap / nav - 1.0, 4),
                    citations=citations,
                )

        attributes = {
            "parent_market_cap": parent_mcap,
            "nav_estimate": nav,
            "discount_pct": discount,
            "subsidiaries": sub_contribs,
        }
        return EnrichmentResult(
            attributes=attributes,
            citations=tuple(citations),
            warnings=tuple(warnings),
            skip_reason=None,
        )


def _skipped_contrib(
    s: Mapping[str, Any], sub_name: str, skip_reason: str
) -> dict[str, Any]:
    return {
        "name": sub_name,
        "stock_code": str(s.get("stock_code") or ""),
        "ownership_pct": float(s.get("ownership_pct") or 0.0),
        "listed": bool(s.get("listed", True)),
        "indirect_via": s.get("indirect_via"),
        "sub_market_cap": None,
        "contribution": None,
        "citation": None,
        "skip_reason": skip_reason,
    }


def _fetch_market_cap(
    *, env: dict[str, str], stock_code: str, fetched_at: str
) -> tuple[float | None, str | None, str | None]:
    """(market_cap, error, citation). G6 — 산식은 본 함수에서만."""
    cache_path = _boundary.resolve_path("kis_token")
    try:
        token = _boundary.kis_issue_access_token(env, cache_path=cache_path)
        out = _boundary.kis_fetch_current_price(
            token=token,
            app_key=env["KIS_APP_KEY"],
            app_secret=env["KIS_APP_SECRET"],
            stock_code=stock_code,
        )
        listed_shares_raw = out.get("lstn_stcn") or "0"
        price_raw = out.get("stck_prpr") or "0"
        listed_shares = float(str(listed_shares_raw).replace(",", "") or "0")
        price = float(str(price_raw).replace(",", "") or "0")
        mcap = listed_shares * price
        if mcap <= 0:
            return None, f"KIS computed mcap=0 (lstn_stcn={listed_shares} prpr={price})", None
        citation = _boundary.format_citation(
            "KIS", fetched_at, {"stock_code": stock_code, "market_cap": mcap}
        )
        return mcap, None, citation
    except _boundary.KisUnavailable as exc:
        return None, f"KIS fail: {exc}", None
    except (ValueError, TypeError, KeyError) as exc:
        return None, f"KIS parse fail: {exc}", None


def _compute_nav(
    *, parent_mcap: float | None, sub_contribs: list[dict[str, Any]]
) -> tuple[float | None, float | None]:
    """NAV = Σ (sub_market_cap × ownership_pct), indirect_via 제외.

    G6 — 본 함수가 산식 single source.
    """
    parts = [
        c["contribution"]
        for c in sub_contribs
        if c.get("contribution") is not None and c.get("indirect_via") is None
    ]
    if not parts:
        return None, None
    nav = sum(parts)
    if not parent_mcap or nav <= 0:
        return nav, None
    discount = round(1.0 - parent_mcap / nav, 4)
    return round(nav, 2), discount
