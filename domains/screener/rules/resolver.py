"""metric_path 화이트리스트 — YAML 이 표현식 DSL 로 미끄러지지 않게.

3 핵심 anchor 중 2: dynamic eval / getattr(snapshot, dynamic_attr) 절대 금지.
새 metric 추가는 본 모듈에 dispatch 분기 추가하는 PR — 의도된 마찰.
편의 위해 register_metric 동적 등록 패턴 제공 (테스트 / 점진 도입용).
"""
from __future__ import annotations

from typing import Callable, Mapping

from domains.screener.domain.ticker import TickerSnapshot
from domains.screener.errors import InsufficientHistoryError, MetricResolutionError

MetricFn = Callable[[TickerSnapshot, "MetricContext"], float]

# Stage 1 enrichment metric 화이트리스트 — dotted ``enrichments.<group>.<key>``.
# eval/getattr 아님: 파싱된 JSON Mapping 을 리터럴 키로 인덱싱. 신규 enrichment
# metric == 여기 한 줄 추가하는 PR (의도된 마찰; _REGISTRY 와 동일 규율).
# key 명칭은 enricher 실제 산출(nav_discount.py / spread_zscore.py)과 정합.
_ENRICHMENT_PREFIX = "enrichments."
_ENRICHMENT_WHITELIST: frozenset[tuple[str, str]] = frozenset(
    {
        ("nav_discount", "discount_pct"),
        ("spread_zscore", "z_score"),
        ("spread_zscore", "catalyst_flag"),
    }
)


class MetricContext:
    """metric 함수에 전달되는 보조 컨텍스트.

    period_years 등 caller (rule) 가 지정하는 parameter 를 묶음.
    Rule 별 config 가 다를 수 있어 contextual injection.
    """

    __slots__ = ("period_years", "tax_rate")

    def __init__(
        self,
        period_years: int | None = None,
        tax_rate: float | None = None,
    ) -> None:
        self.period_years = period_years
        self.tax_rate = tax_rate


_REGISTRY: dict[str, MetricFn] = {}


def register_metric(name: str) -> Callable[[MetricFn], MetricFn]:
    """metric_path 화이트리스트에 함수 등록. 중복 등록은 ValueError."""

    def deco(fn: MetricFn) -> MetricFn:
        if name in _REGISTRY:
            raise ValueError(f"metric '{name}' already registered")
        _REGISTRY[name] = fn
        return fn

    return deco


def resolve_metric(
    snapshot: TickerSnapshot,
    path: str,
    *,
    period_years: int | None = None,
    tax_rate: float | None = None,
) -> float:
    """metric_path → snapshot 의 derived 값. 등록되지 않은 path 는 raise.

    ``enrichments.<group>.<key>`` prefix 는 Stage 1 enrichment 화이트리스트 분기로
    해석 (exact-match _REGISTRY 와 별개). 그 외는 기존 _REGISTRY dispatch.
    """
    if path.startswith(_ENRICHMENT_PREFIX):
        return _resolve_enrichment(snapshot, path)
    fn = _REGISTRY.get(path)
    if fn is None:
        raise MetricResolutionError(f"unknown metric_path: {path}")
    ctx = MetricContext(period_years=period_years, tax_rate=tax_rate)
    return fn(snapshot, ctx)


def _resolve_enrichment(snapshot: TickerSnapshot, path: str) -> float:
    """``enrichments.<group>.<key>`` → snapshot.enrichments 의 리터럴 인덱싱.

    getattr/eval 절대 금지 — 화이트리스트 게이트 후 파싱된 dict 인덱싱만.
    결측 / 비화이트리스트 / None 값은 MetricResolutionError → leaf 가 data_missing
    (false pass 방지).
    """
    parts = path[len(_ENRICHMENT_PREFIX):].split(".")
    if len(parts) != 2:
        raise MetricResolutionError(f"enrichments.<group>.<key> 형식 위반: {path}")
    group, key = parts
    if (group, key) not in _ENRICHMENT_WHITELIST:
        raise MetricResolutionError(f"enrichment metric not whitelisted: {group}.{key}")
    group_map = snapshot.enrichments.get(group)
    if not isinstance(group_map, Mapping) or key not in group_map:
        raise MetricResolutionError(f"enrichment data missing: {group}.{key}")
    v = group_map[key]
    if v is None:
        raise MetricResolutionError(f"enrichment value None: {group}.{key}")
    return float(v)  # bool->float (catalyst_flag = 1.0/0.0)


# ----------------------------------------------------------------------
# 등록된 metric — 새 metric 은 본 섹션에 한 줄 추가하는 PR
# ----------------------------------------------------------------------


@register_metric("annuals_avg.roic")
def _roic_avg(snapshot: TickerSnapshot, ctx: MetricContext) -> float:
    if ctx.tax_rate is None:
        raise MetricResolutionError("annuals_avg.roic 은 tax_rate 필요")
    years = ctx.period_years or 3
    return snapshot.annual_roic_avg(tax_rate=ctx.tax_rate, years=years)


@register_metric("ttm.fcf_to_revenue")
def _ttm_fcf_to_revenue(snapshot: TickerSnapshot, ctx: MetricContext) -> float:
    v = snapshot.ttm_fcf_to_revenue()
    if v is None:
        raise InsufficientHistoryError("ttm.fcf_to_revenue: 데이터 부재")
    return v


@register_metric("latest_annual.debt_to_equity")
def _debt_to_equity(snapshot: TickerSnapshot, ctx: MetricContext) -> float:
    v = snapshot.debt_to_equity_latest()
    if v is None:
        raise InsufficientHistoryError("latest_annual.debt_to_equity: 데이터 부재")
    return v


@register_metric("latest_annual.interest_coverage")
def _interest_coverage(snapshot: TickerSnapshot, ctx: MetricContext) -> float:
    v = snapshot.interest_coverage_latest()
    if v is None:
        raise InsufficientHistoryError("latest_annual.interest_coverage: 데이터 부재")
    return v


@register_metric("fcf_positive_years")
def _fcf_positive_years(snapshot: TickerSnapshot, ctx: MetricContext) -> float:
    years = ctx.period_years or 3
    return float(snapshot.fcf_positive_years(years))


@register_metric("signals.count")
def _signals_count(snapshot: TickerSnapshot, ctx: MetricContext) -> float:
    return float(len(snapshot.capital_allocation_signals))
