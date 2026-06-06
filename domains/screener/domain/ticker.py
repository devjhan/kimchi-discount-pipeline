"""TickerSnapshot — 시점 t 에서 가시적인 종목의 재무 데이터 묶음.

설계 원칙:
- clock 시점 이전 공시만 포함 (IO layer 책임; domain 객체는 시간 의식 X)
- 같은 fiscal_period 의 정정 공시는 가장 늦은 visible 1개로 압축
- annuals / interims 는 period_end_date 오름차순 정렬
- 모든 derived metric 은 본 클래스 메서드에서만 계산 → G6 helper 단독 규칙
- all_citations() 로 사용된 모든 출처를 RuleResult 에 전파 → G7 준수
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Literal, Mapping

from domains.screener.errors import InsufficientHistoryError
from domains._shared.time.clock import AsOfClock

FiscalKind = Literal["annual", "half", "quarter"]


@dataclass(frozen=True)
class FilingMetric:
    """단일 DART 공시에서 추출된 재무 항목 묶음.

    raw IFRS 표준 명칭 그대로 보관 — 변환은 caller (rule) 의 책임.
    """

    fiscal_period: str
    period_end_date: date
    filing_datetime: datetime
    kind: FiscalKind
    is_amended: bool

    revenue: float | None = None
    operating_income: float | None = None
    net_income: float | None = None
    total_assets: float | None = None
    total_equity: float | None = None
    total_debt: float | None = None
    finance_costs: float | None = None
    operating_cash_flow: float | None = None
    capex: float | None = None

    citation: str = ""


@dataclass(frozen=True)
class TickerSnapshot:
    """시점 t 에서 가시적인 모든 filing 묶음 + derived metric API."""

    ticker: str
    name: str
    clock: AsOfClock

    annuals: tuple[FilingMetric, ...] = field(default_factory=tuple)
    interims: tuple[FilingMetric, ...] = field(default_factory=tuple)
    capital_allocation_signals: tuple[str, ...] = field(default_factory=tuple)
    universe_citation: str = ""

    enrichments: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    """{group: {key: value}} — Stage 1 universe 의 EnrichedEntry.enrichments 미러.
    point-in-time (캐시 미저장) — screen.run_screen 이 매 run 런타임 주입.
    default 빈 dict → 기존 생성부 전부 호환 (동작 변화 0)."""

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    @property
    def latest_annual(self) -> FilingMetric | None:
        """가장 최근 annual filing. 없으면 None."""
        return self.annuals[-1] if self.annuals else None

    @property
    def latest_interim(self) -> FilingMetric | None:
        """가장 최근 interim filing. 없으면 None."""
        return self.interims[-1] if self.interims else None

    # ------------------------------------------------------------------
    # Derived metrics (G6 — 산술 계산은 본 클래스에서만)
    # ------------------------------------------------------------------

    def annual_series(self, attr: str, years: int) -> list[float]:
        """최근 N년치 attribute 시계열. 데이터 부족 / None 시 raise."""
        if len(self.annuals) < years:
            raise InsufficientHistoryError(
                f"{self.ticker}: {attr} 시계열 부족 "
                f"(have={len(self.annuals)}, need={years})"
            )
        out: list[float] = []
        for f in self.annuals[-years:]:
            v = getattr(f, attr, None)
            if v is None:
                raise InsufficientHistoryError(
                    f"{self.ticker}: {f.fiscal_period}.{attr} = None"
                )
            out.append(float(v))
        return out

    def annual_avg(self, attr: str, years: int) -> float:
        """최근 N년 평균. annual_series 의 산술 평균."""
        series = self.annual_series(attr, years)
        return sum(series) / len(series)

    def annual_roic(self, *, tax_rate: float, year_offset: int = 0) -> float:
        """ROIC = NOPAT / Invested Capital. tax_rate 는 config 에서 주입."""
        if not self.annuals:
            raise InsufficientHistoryError(f"{self.ticker}: annual filing 부재")
        idx = -1 - year_offset
        if -idx > len(self.annuals):
            raise InsufficientHistoryError(
                f"{self.ticker}: year_offset={year_offset} 의 annual filing 부재"
            )
        f = self.annuals[idx]
        invested = (f.total_equity or 0) + (f.total_debt or 0)
        if invested <= 0 or f.operating_income is None:
            raise InsufficientHistoryError(f"{self.ticker}: ROIC 계산 불가")
        nopat = f.operating_income * (1.0 - tax_rate)
        return nopat / invested

    def annual_roic_series(self, *, tax_rate: float, years: int) -> list[float]:
        """최근 N년 ROIC 시계열."""
        if len(self.annuals) < years:
            raise InsufficientHistoryError(
                f"{self.ticker}: ROIC {years}년치 부족 "
                f"(have={len(self.annuals)})"
            )
        return [
            self.annual_roic(tax_rate=tax_rate, year_offset=i)
            for i in reversed(range(years))
        ]

    def annual_roic_avg(self, *, tax_rate: float, years: int) -> float:
        """최근 N년 ROIC 평균."""
        series = self.annual_roic_series(tax_rate=tax_rate, years=years)
        return sum(series) / len(series)

    def fcf_recent(self) -> float | None:
        """가장 최근 annual 의 FCF = OpCF − CapEx. 부재 시 None."""
        f = self.latest_annual
        if f is None or f.operating_cash_flow is None or f.capex is None:
            return None
        return f.operating_cash_flow - f.capex

    def fcf_positive_years(self, years: int) -> int:
        """최근 N년 중 FCF 양수 연도 수 (annual 시계열 한정)."""
        count = 0
        for f in self.annuals[-years:]:
            if f.operating_cash_flow is not None and f.capex is not None:
                if (f.operating_cash_flow - f.capex) > 0:
                    count += 1
        return count

    def ttm_revenue(self) -> float | None:
        """Trailing 12 months 매출. 최신 4 interims 합산 가능 시 사용."""
        if not self.annuals and not self.interims:
            return None
        if len(self.interims) >= 4 and all(
            i.revenue is not None for i in self.interims[-4:]
        ):
            return sum(float(i.revenue) for i in self.interims[-4:])  # type: ignore[arg-type]
        return self.latest_annual.revenue if self.latest_annual else None

    def ttm_fcf_to_revenue(self) -> float | None:
        """TTM FCF / Revenue. 분모 0 또는 데이터 부재 시 None."""
        rev = self.ttm_revenue()
        fcf = self.fcf_recent()
        if rev is None or fcf is None or rev == 0:
            return None
        return fcf / rev

    def debt_to_equity_latest(self) -> float | None:
        """가장 최근 annual 의 D/E. 분모 부재 시 None."""
        f = self.latest_annual
        if f is None or f.total_equity is None or f.total_equity == 0:
            return None
        return (f.total_debt or 0) / f.total_equity

    def interest_coverage_latest(self) -> float | None:
        """가장 최근 annual 의 이자보상배율. finance_costs 부재 시 None."""
        f = self.latest_annual
        if f is None or f.operating_income is None or not f.finance_costs:
            return None
        return f.operating_income / f.finance_costs

    # ------------------------------------------------------------------
    # G7 — 사용된 모든 citation 전파
    # ------------------------------------------------------------------

    def all_citations(self) -> tuple[str, ...]:
        """본 snapshot 에 포함된 모든 filing + universe citation 의 합."""
        cits: list[str] = []
        if self.universe_citation:
            cits.append(self.universe_citation)
        cits.extend(f.citation for f in self.annuals if f.citation)
        cits.extend(f.citation for f in self.interims if f.citation)
        return tuple(cits)
