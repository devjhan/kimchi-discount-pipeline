"""SpreadZScoreEnricher — 우선주/보통주 스프레드 z-score attach.

원래 ``stage1_pref_spread.py:202-380`` (compute_spread_series + compute_zscore +
evaluate_pair) 의 Enricher plugin 이전. applies_to={"preferred_share_pair"} —
PreferredShareSeedSource 가 emit 한 entry 의 metadata.{common,preferred,market}
을 읽어 KIS (또는 Yahoo fallback) 일봉 series 로 spread 시계열 + z-score 계산.

attributes: common_close / preferred_close / current_spread_pct / mean_spread_pct /
std_spread_pct / z_score / z_min / catalyst_flag / n_observations / price_source.

config (enrichers.yaml entry): lookback_days / min_observations / z_min.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping

from domains.universe import _boundary
from domains.universe.domain.enriched import EnrichmentResult
from domains.universe.domain.entry import UniverseEntry
from domains.universe.enrichers.base import EnrichContext, Enricher
from domains.universe.enrichers.registry import register_enricher

_KIS_CHUNK_DAYS = 100  # KIS hard cap


@register_enricher("spread_zscore")
@dataclass(frozen=True)
class SpreadZScoreEnricher(Enricher):
    """common - preferred 스프레드의 historical z-score (mean-reversion entry signal)."""

    name: str
    lookback_days: int = 750
    min_observations: int = 600
    z_min: float = 1.5
    applies_to: frozenset[str] = frozenset({"preferred_share_pair"})

    @classmethod
    def from_spec(cls, spec: dict[str, Any]) -> "SpreadZScoreEnricher":
        applies_to_raw = spec.get("applies_to") or ["preferred_share_pair"]
        return cls(
            name=spec["name"],
            lookback_days=int(spec.get("lookback_days", 750)),
            min_observations=int(spec.get("min_observations", 600)),
            z_min=float(spec.get("z_min", 1.5)),
            applies_to=frozenset(str(c) for c in applies_to_raw),
        )

    def enrich(self, entry: UniverseEntry, ctx: EnrichContext) -> EnrichmentResult:
        md = dict(entry.metadata or {})
        common = str(md.get("common") or "").strip()
        preferred = str(md.get("preferred") or "").strip()
        market = str(md.get("market") or "KOSPI")
        if not common or not preferred:
            return EnrichmentResult(
                attributes={},
                citations=(),
                warnings=(),
                skip_reason="entry.metadata 에 common / preferred ticker 부재",
            )

        env = dict(ctx.env)
        fetched_at = _boundary.now_iso_kst()
        citations: list[str] = []
        warnings: list[str] = []
        end_date_str = ctx.clock.trading_date.strftime("%Y%m%d")

        common_series, common_err, common_src, common_cite = _fetch_series(
            env=env,
            stock_code=common,
            market=market,
            end_date=end_date_str,
            period_days=self.lookback_days,
            allow_yahoo=ctx.allow_yahoo,
            fetched_at=fetched_at,
        )
        pref_series, pref_err, pref_src, pref_cite = _fetch_series(
            env=env,
            stock_code=preferred,
            market=market,
            end_date=end_date_str,
            period_days=self.lookback_days,
            allow_yahoo=ctx.allow_yahoo,
            fetched_at=fetched_at,
        )
        if common_cite:
            citations.append(common_cite)
        if pref_cite:
            citations.append(pref_cite)

        if common_series is None or pref_series is None:
            errs = []
            if common_err:
                errs.append(f"common({common}): {common_err}")
            if pref_err:
                errs.append(f"preferred({preferred}): {pref_err}")
            return EnrichmentResult(
                attributes={
                    "price_source": "unavailable",
                    "n_observations": 0,
                    "z_min": self.z_min,
                    "catalyst_flag": False,
                },
                citations=tuple(citations),
                warnings=tuple(warnings),
                skip_reason=f"가격 series fetch 실패 — {'; '.join(errs) or 'unknown'}",
            )

        price_source = "Yahoo" if (common_src == "Yahoo" or pref_src == "Yahoo") else "KIS"

        spread_series = _compute_spread_series(common_series, pref_series)
        if not spread_series:
            return EnrichmentResult(
                attributes={
                    "price_source": price_source,
                    "n_observations": 0,
                    "z_min": self.z_min,
                    "catalyst_flag": False,
                },
                citations=tuple(citations),
                warnings=tuple(warnings),
                skip_reason="common / preferred 공통 거래일 0개",
            )

        last_date, current_spread = spread_series[-1]
        history = spread_series[:-1]
        mean, std, z = _compute_zscore(
            history, current_spread, min_observations=self.min_observations
        )

        catalyst_flag = bool(z is not None and abs(z) >= self.z_min)
        attributes: dict[str, Any] = {
            "common_close": common_series[-1][1] if common_series else None,
            "preferred_close": pref_series[-1][1] if pref_series else None,
            "current_spread_pct": current_spread,
            "mean_spread_pct": mean,
            "std_spread_pct": std,
            "z_score": z,
            "z_min": self.z_min,
            "catalyst_flag": catalyst_flag,
            "n_observations": len(history),
            "price_source": price_source,
            "last_observation_date": last_date,
        }
        return EnrichmentResult(
            attributes=attributes,
            citations=tuple(citations),
            warnings=tuple(warnings),
            skip_reason=None,
        )


# ----------------------------------------------------------------------
# Price series fetch — KIS 우선, Yahoo fallback
# ----------------------------------------------------------------------


def _fetch_series(
    *,
    env: dict[str, str],
    stock_code: str,
    market: str,
    end_date: str,
    period_days: int,
    allow_yahoo: bool,
    fetched_at: str,
) -> tuple[list[tuple[str, float]] | None, str | None, str | None, str | None]:
    """(series, error, source, citation). source ∈ {'KIS', 'Yahoo'}."""
    kis_series, kis_err = _kis_close_series(
        env=env, stock_code=stock_code, end_date=end_date, period_days=period_days
    )
    if kis_series is not None:
        citation = _boundary.format_citation(
            "KIS", fetched_at, {"stock_code": stock_code, "n_obs": len(kis_series)}
        )
        return kis_series, None, "KIS", citation
    if not allow_yahoo:
        return None, kis_err, None, None
    yahoo_series, yahoo_err = _yahoo_close_series(
        stock_code=stock_code, market=market, period_days=period_days
    )
    if yahoo_series is not None:
        citation = _boundary.format_citation(
            "Yahoo", fetched_at, {"stock_code": stock_code, "n_obs": len(yahoo_series)}
        )
        return yahoo_series, None, "Yahoo", citation
    combined_err = f"KIS: {kis_err}; Yahoo: {yahoo_err}"
    return None, combined_err, None, None


def _kis_close_series(
    *, env: dict[str, str], stock_code: str, end_date: str, period_days: int
) -> tuple[list[tuple[str, float]] | None, str | None]:
    """KIS 일봉 (100일 분할). returns sorted [(yyyymmdd, close), ...]."""
    if not _boundary.kis_has_keys(env):
        return None, "KIS_APP_KEY/SECRET missing"
    cache_path = _boundary.resolve_path("kis_token")
    try:
        token = _boundary.kis_issue_access_token(env, cache_path=cache_path)
    except _boundary.KisUnavailable as exc:
        return None, f"KIS token issue fail: {exc}"

    rows: list[dict[str, Any]] = []
    cursor_end = end_date
    fetched = 0
    while fetched < period_days:
        chunk_size = min(_KIS_CHUNK_DAYS, period_days - fetched)
        try:
            chunk = _boundary.kis_fetch_daily_ohlcv(
                token=token,
                app_key=env["KIS_APP_KEY"],
                app_secret=env["KIS_APP_SECRET"],
                stock_code=stock_code,
                period_days=chunk_size,
                end_date=cursor_end,
            )
        except _boundary.KisUnavailable as exc:
            return None, f"KIS fail at cursor={cursor_end}: {exc}"
        if not chunk:
            break
        rows.extend(chunk)
        fetched += len(chunk)
        oldest = min((r.get("stck_bsop_date") or "") for r in chunk)
        if not oldest or len(oldest) != 8:
            break
        from datetime import datetime as _dt
        from datetime import timedelta as _td

        try:
            d = _dt.strptime(oldest, "%Y%m%d") - _td(days=1)
            cursor_end = d.strftime("%Y%m%d")
        except ValueError:
            break

    if not rows:
        return None, "KIS returned 0 rows"

    seen: set[str] = set()
    out: list[tuple[str, float]] = []
    for r in rows:
        d = r.get("stck_bsop_date") or ""
        c_raw = r.get("stck_clpr") or ""
        if not d or d in seen:
            continue
        seen.add(d)
        try:
            c = float(str(c_raw).replace(",", ""))
        except ValueError:
            continue
        out.append((d, c))
    out.sort(key=lambda x: x[0])
    return out, None


def _yahoo_close_series(
    *, stock_code: str, market: str, period_days: int
) -> tuple[list[tuple[str, float]] | None, str | None]:
    try:
        ticker = _boundary.yahoo_krx_to_yahoo(stock_code, market)
        rows = _boundary.yahoo_fetch_daily_ohlcv(ticker, period_days=period_days)
    except _boundary.YahooUnavailable as exc:
        return None, f"Yahoo fail: {exc}"
    out: list[tuple[str, float]] = []
    for r in rows:
        d = r.get("date") or ""
        c = r.get("close")
        if not d or c is None:
            continue
        try:
            out.append((str(d).replace("-", ""), float(c)))
        except (TypeError, ValueError):
            continue
    out.sort(key=lambda x: x[0])
    return out, None


# ----------------------------------------------------------------------
# G6 — 산식 single source
# ----------------------------------------------------------------------


def _compute_spread_series(
    common: list[tuple[str, float]], preferred: list[tuple[str, float]]
) -> list[tuple[str, float]]:
    """공통 거래일 기준 spread = (common - pref) / common."""
    cmap = dict(common)
    out: list[tuple[str, float]] = []
    for d, p in preferred:
        c = cmap.get(d)
        if c is None or c <= 0:
            continue
        out.append((d, (c - p) / c))
    return out


def _compute_zscore(
    series: list[tuple[str, float]], current: float, *, min_observations: int
) -> tuple[float | None, float | None, float | None]:
    """(mean, std, z). std=0 또는 N<min_observations 이면 z=None."""
    if len(series) < min_observations:
        return None, None, None
    vals = [v for _, v in series]
    n = len(vals)
    mean = sum(vals) / n
    var = sum((x - mean) ** 2 for x in vals) / max(n - 1, 1)
    std = math.sqrt(var)
    if std == 0:
        return mean, std, None
    z = (current - mean) / std
    return mean, std, z
