"""Point-in-time financial cache — Live 와 PointInTime 두 구현.

DDD anti-corruption: 외부 file system 의 cache JSON 을 도메인 객체
(``TickerSnapshot``) 로 변환. 두 구현은 ``FinancialCacheBase`` ABC 를 공유.

Live cache (per-ticker 단일 파일):
- 일별 cron 의 실제 사용처. schema = v4 만.
- v4 가 아닌 cache 는 schema mismatch 로 miss 처리 → 다음 fetch 에서 v4 overwrite.
- **clock 은 오늘 (KST) 만 허용** — 과거 clock 으로 get_snapshot 호출 시 ValueError.
  과거 시점 가시화는 PointInTimeFinancialCache 의 책임. 백테스트 lookahead bias 방어.

PointInTime cache (per-ticker × fiscal_period × filing_datetime 다중 파일):
- 백테스트 결정론. ``clock.can_see(filing_datetime)`` 으로 가시 필터.
- Phase 2 (백테스트 도입) 에서 본 구현. PR2 단계는 stub.
"""
from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from domains.screener import _boundary
from domains.screener.domain.ticker import FilingMetric, TickerSnapshot
from domains.screener.io.capital_signals_cache import filter_visible_signals
from domains.screener.schemas import SCHEMA_FIN_CACHE_V4
from domains._shared.time.clock import AsOfClock


@dataclass(frozen=True)
class CachePolicy:
    """TTL / grace 정책. screener config/thresholds.yaml 에서 주입."""

    financials_ttl_days: int
    capital_signals_ttl_days: int
    staleness_grace_days: int

    @property
    def financials_ttl_seconds(self) -> int:
        return self.financials_ttl_days * 86_400

    @property
    def capital_signals_ttl_seconds(self) -> int:
        return self.capital_signals_ttl_days * 86_400

    @property
    def grace_seconds(self) -> int:
        return self.staleness_grace_days * 86_400


class FinancialCacheBase(ABC):
    """Live / PointInTime 공통 인터페이스."""

    @abstractmethod
    def get_snapshot(
        self, ticker: str, name: str, clock: AsOfClock
    ) -> TickerSnapshot | None:
        """ticker / clock 기준 TickerSnapshot. cache miss 또는 v3-only 면 None."""

    @abstractmethod
    def is_fresh(self, ticker: str, layer: str, now_epoch: int) -> bool:
        """layer ∈ {financials, capital_signals} 의 TTL 신선도."""


class LiveFinancialCache(FinancialCacheBase):
    """일별 cron 의 latest cache. per-ticker 단일 파일 (``KR_{code}.json``).

    schema v3 (legacy) 와 v4 (raw filing 포함) 모두 read. write 는 v4 만.
    """

    def __init__(self, base_dir: Path, *, policy: CachePolicy) -> None:
        self._base_dir = base_dir
        self._policy = policy

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_snapshot(
        self, ticker: str, name: str, clock: AsOfClock
    ) -> TickerSnapshot | None:
        """raw JSON → TickerSnapshot. schema != v4 또는 miss 면 None.

        Raises:
            ValueError: clock.trading_date 가 KST 오늘이 아닐 때.
                LiveFinancialCache 는 "현재 시점 latest" 만 처리한다.
                과거 시점 가시화 (백테스트) 는 PointInTimeFinancialCache 책임.
        """
        today = _boundary.now_kst().date()
        if clock.trading_date != today:
            raise ValueError(
                f"LiveFinancialCache 는 오늘 ({today}) 의 clock 만 지원. "
                f"clock.trading_date={clock.trading_date}. "
                "과거 시점 평가는 PointInTimeFinancialCache 를 사용하세요."
            )

        cached = self._read_raw(ticker)
        if cached is None:
            return None

        if str(cached.get("schema", "")) != SCHEMA_FIN_CACHE_V4:
            # legacy / unknown schema → miss. 다음 fetch 에서 v4 로 overwrite.
            return None

        annuals = _load_filings(cached.get("filings") or [], kind_filter="annual")
        interims = _load_filings(
            cached.get("filings") or [], kind_filter=("half", "quarter")
        )
        visible_signals = filter_visible_signals(
            cached.get("capital_signals_events") or [], clock
        )
        return TickerSnapshot(
            ticker=ticker,
            name=name,
            clock=clock,
            annuals=annuals,
            interims=interims,
            capital_allocation_signals=visible_signals,
            universe_citation=str(cached.get("universe_citation") or ""),
        )

    def read_raw(self, ticker: str) -> dict[str, Any] | None:
        """cache JSON 원본 — caller 가 metadata (corp_code, prev_meta) 활용."""
        return self._read_raw(ticker)

    def _read_raw(self, ticker: str) -> dict[str, Any] | None:
        path = self._cache_path(ticker)
        if not path.exists():
            return None
        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return None
            return data
        except (OSError, json.JSONDecodeError):
            return None

    # ------------------------------------------------------------------
    # TTL / freshness
    # ------------------------------------------------------------------

    def is_fresh(self, ticker: str, layer: str, now_epoch: int) -> bool:
        """layer ∈ {financials, capital_signals}. cache miss 면 False."""
        cached = self._read_raw(ticker)
        if cached is None:
            return False
        return _is_layer_fresh(cached, layer, now_epoch)

    def is_within_grace(self, ticker: str, layer: str, now_epoch: int) -> bool:
        """TTL 만료 + grace 이내. G8 graceful fallback 진입 조건."""
        cached = self._read_raw(ticker)
        if cached is None:
            return False
        return _is_within_grace(
            cached, layer, now_epoch, self._policy.grace_seconds
        )

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def write_atomic(
        self,
        ticker: str,
        *,
        name: str,
        corp_code: str,
        bsns_year: str,
        tax_rate: float,
        filings: list[FilingMetric],
        capital_signals_events: list[dict[str, Any]],
        metrics: dict[str, Any],
        citations: list[str],
        universe_citation: str = "",
        now_epoch: int | None = None,
        prev_meta: dict[str, Any] | None = None,
        update_financials: bool = True,
        update_capital_signals: bool = True,
    ) -> Path:
        """v4 schema 로 atomic cache 갱신. ``tmp + rename`` 패턴.

        ``write_output_safely`` 의 ``.{N}.json`` suffix 는 cache 에 부적합 —
        매일 동일 path 갱신 의도. infrastructure/dart/client.py 의 corp_code
        atomic write 패턴 직역.
        """
        now_epoch = int(now_epoch if now_epoch is not None else time.time())
        fetched_at_iso = _boundary.now_iso_kst()
        payload: dict[str, Any] = {
            "schema": SCHEMA_FIN_CACHE_V4,
            "ticker": ticker,
            "name": name,
            "corp_code": corp_code,
            "fetched_at": fetched_at_iso,
            "bsns_year": bsns_year,
            "tax_rate": tax_rate,
            "_cache_meta": _build_cache_meta(
                now_epoch=now_epoch,
                fetched_at_iso=fetched_at_iso,
                financials_ttl_s=self._policy.financials_ttl_seconds,
                capital_signals_ttl_s=self._policy.capital_signals_ttl_seconds,
                prev_meta=prev_meta,
                update_financials=update_financials,
                update_capital_signals=update_capital_signals,
            ),
            "universe_citation": universe_citation
            or str((prev_meta or {}).get("universe_citation", ""))
            or str(self._prev_universe_citation(ticker)),
            "filings": [_dump_filing(f) for f in filings],
            "capital_signals_events": list(capital_signals_events),
            "metrics": dict(metrics),
            "citations": list(citations),
        }
        path = self._cache_path(ticker)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        tmp.replace(path)
        return path

    # ------------------------------------------------------------------
    # Path
    # ------------------------------------------------------------------

    def _cache_path(self, ticker: str) -> Path:
        """ticker → file path. ``KR:005930`` → ``KR_005930.json``."""
        safe = ticker.replace(":", "_")
        return self._base_dir / f"{safe}.json"

    def _prev_universe_citation(self, ticker: str) -> str:
        """기존 cache 의 universe_citation 보존 — refetch 시 손실 방어."""
        prev = self._read_raw(ticker)
        if prev is None:
            return ""
        return str(prev.get("universe_citation") or "")


class PointInTimeFinancialCache(FinancialCacheBase):
    """백테스트용 PIT cache — Phase 2 본 구현. PR2 는 stub.

    ``{base_dir}/{ticker_safe}/{fiscal_period}/{filing_datetime}.json``
    다중 파일 layout. clock.can_see(filing_datetime) 으로 가시 필터.
    """

    def __init__(self, base_dir: Path) -> None:
        self._base_dir = base_dir

    def get_snapshot(
        self, ticker: str, name: str, clock: AsOfClock
    ) -> TickerSnapshot | None:
        """Phase 2 본 구현. PR2 단계는 항상 None."""
        return None

    def is_fresh(self, ticker: str, layer: str, now_epoch: int) -> bool:
        return False


# ----------------------------------------------------------------------
# 내부 helper — stage2_fin_fetch.py 직역
# ----------------------------------------------------------------------


def _is_layer_fresh(
    cached: dict[str, Any], layer: str, now_epoch: int
) -> bool:
    """``_cache_meta[layer].{fetched_at_epoch, ttl_seconds}`` 신선도."""
    meta = cached.get("_cache_meta")
    if not isinstance(meta, dict):
        return False
    layer_meta = meta.get(layer)
    if not isinstance(layer_meta, dict):
        return False
    try:
        fetched_at = int(layer_meta.get("fetched_at_epoch", 0))
        ttl = int(layer_meta.get("ttl_seconds", 0))
    except (TypeError, ValueError):
        return False
    if fetched_at <= 0 or ttl <= 0:
        return False
    return (now_epoch - fetched_at) < ttl


def _is_within_grace(
    cached: dict[str, Any], layer: str, now_epoch: int, grace_seconds: int
) -> bool:
    """TTL 만료 + grace 이내. DART fail 시 stale fallback 게이트."""
    meta = cached.get("_cache_meta")
    if not isinstance(meta, dict):
        return False
    layer_meta = meta.get(layer)
    if not isinstance(layer_meta, dict):
        return False
    try:
        fetched_at = int(layer_meta.get("fetched_at_epoch", 0))
        ttl = int(layer_meta.get("ttl_seconds", 0))
    except (TypeError, ValueError):
        return False
    if fetched_at <= 0 or ttl <= 0:
        return False
    age = now_epoch - fetched_at
    return ttl <= age < (ttl + grace_seconds)


def _build_cache_meta(
    *,
    now_epoch: int,
    fetched_at_iso: str,
    financials_ttl_s: int,
    capital_signals_ttl_s: int,
    prev_meta: dict[str, Any] | None,
    update_financials: bool,
    update_capital_signals: bool,
) -> dict[str, Any]:
    """``_cache_meta`` 블록 구성. update_* False 시 prev_meta 값 보존."""

    def _layer(update: bool, ttl_s: int, key: str) -> dict[str, Any]:
        if update:
            return {
                "fetched_at": fetched_at_iso,
                "fetched_at_epoch": int(now_epoch),
                "ttl_seconds": int(ttl_s),
            }
        if prev_meta and isinstance(prev_meta.get(key), dict):
            return dict(prev_meta[key])
        return {"fetched_at": "", "fetched_at_epoch": 0, "ttl_seconds": int(ttl_s)}

    return {
        "financials": _layer(update_financials, financials_ttl_s, "financials"),
        "capital_signals": _layer(
            update_capital_signals, capital_signals_ttl_s, "capital_signals"
        ),
    }


def _load_filings(
    raw_filings: list[dict[str, Any]],
    *,
    kind_filter: str | tuple[str, ...],
) -> tuple[FilingMetric, ...]:
    """v4 cache 의 ``filings[]`` → FilingMetric tuple. kind 필터 + 시간 정렬."""
    kinds = (
        (kind_filter,) if isinstance(kind_filter, str) else tuple(kind_filter)
    )
    out: list[FilingMetric] = []
    for raw in raw_filings:
        kind = raw.get("kind")
        if kind not in kinds:
            continue
        try:
            period_end = datetime.fromisoformat(raw["period_end_date"]).date()
            filing_dt = datetime.fromisoformat(raw["filing_datetime"])
        except (KeyError, ValueError):
            continue
        out.append(
            FilingMetric(
                fiscal_period=raw["fiscal_period"],
                period_end_date=period_end,
                filing_datetime=filing_dt,
                kind=kind,  # type: ignore[arg-type]
                is_amended=bool(raw.get("is_amended", False)),
                revenue=_opt_float(raw.get("revenue")),
                operating_income=_opt_float(raw.get("operating_income")),
                net_income=_opt_float(raw.get("net_income")),
                total_assets=_opt_float(raw.get("total_assets")),
                total_equity=_opt_float(raw.get("total_equity")),
                total_debt=_opt_float(raw.get("total_debt")),
                finance_costs=_opt_float(raw.get("finance_costs")),
                operating_cash_flow=_opt_float(raw.get("operating_cash_flow")),
                capex=_opt_float(raw.get("capex")),
                citation=str(raw.get("citation", "")),
            )
        )
    return tuple(sorted(out, key=lambda f: f.period_end_date))


def _dump_filing(f: FilingMetric) -> dict[str, Any]:
    """FilingMetric → JSON-serializable dict."""
    return {
        "fiscal_period": f.fiscal_period,
        "period_end_date": f.period_end_date.isoformat(),
        "filing_datetime": f.filing_datetime.isoformat(timespec="seconds"),
        "kind": f.kind,
        "is_amended": f.is_amended,
        "revenue": f.revenue,
        "operating_income": f.operating_income,
        "net_income": f.net_income,
        "total_assets": f.total_assets,
        "total_equity": f.total_equity,
        "total_debt": f.total_debt,
        "finance_costs": f.finance_costs,
        "operating_cash_flow": f.operating_cash_flow,
        "capex": f.capex,
        "citation": f.citation,
    }


def _opt_float(v: Any) -> float | None:
    """JSON 값 → optional float. 변환 실패 시 None."""
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def policy_from_strategy(strategy_yaml: dict[str, Any]) -> CachePolicy:
    """strategy YAML 의 ``constants.financial_cache`` 섹션 → CachePolicy."""
    fc = (strategy_yaml.get("constants") or {}).get("financial_cache") or {}
    return CachePolicy(
        financials_ttl_days=int(fc.get("financials_ttl_days", 30)),
        capital_signals_ttl_days=int(fc.get("capital_signals_ttl_days", 7)),
        staleness_grace_days=int(fc.get("staleness_grace_days", 14)),
    )
