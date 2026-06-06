"""DART API → screener domain 객체 변환 어댑터 (anti-corruption layer).

직접 HTTP 호출 / infrastructure 직접 import 일체 금지 — 모든 외부 호출은
``_boundary.dart_*`` 위임 함수만 사용.

본 모듈은 DART 응답의 raw 표현을 screener 의 도메인 객체
(``FilingMetric`` / capital_signals_events) 로 변환하는 것이 단일 책임.
ROIC / FCF / D/E / interest_coverage 같은 derived metric 산출 자체는 도메인
객체 (``TickerSnapshot``) 의 메서드에서. metrics dict 는 brief author 의
빠른 인용용 보조 산출.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from domains.screener import _boundary
from domains.screener.domain.ticker import FilingMetric
from domains._shared.ports.citation import CitationPort


# ----------------------------------------------------------------------
# DART account_nm / account_id 화이트리스트
# (stage2_fin_fetch.py:84-128 직역)
# ----------------------------------------------------------------------

ACCT_REVENUE = ("매출액", "수익(매출액)", "영업수익", "매출", "수익")
ACCT_REVENUE_IDS = ("ifrs-full_Revenue",)

ACCT_OPERATING_INCOME = ("영업이익", "영업이익(손실)", "영업손익")
ACCT_OPERATING_INCOME_IDS = (
    "dart_OperatingIncomeLoss",
    "ifrs-full_ProfitLossFromOperatingActivities",
)

ACCT_NET_INCOME = ("당기순이익", "당기순이익(손실)", "당기순손익")
ACCT_NET_INCOME_IDS = ("ifrs-full_ProfitLoss",)

ACCT_TOTAL_EQUITY = ("자본총계",)
ACCT_TOTAL_EQUITY_IDS = ("ifrs-full_Equity",)

ACCT_TOTAL_LIABILITIES = ("부채총계",)
ACCT_TOTAL_LIABILITIES_IDS = ("ifrs-full_Liabilities",)

ACCT_INTEREST_EXPENSE = (
    "금융비용",
    "이자비용",
    "기타금융비용",
    "이자비용(금융비용)",
    "금융원가",
)
ACCT_INTEREST_EXPENSE_IDS = (
    "ifrs-full_FinanceCosts",
    "ifrs-full_InterestExpense",
    "dart_FinanceCosts",
)

ACCT_OPERATING_CF = ("영업활동현금흐름", "영업활동으로 인한 현금흐름")
ACCT_OPERATING_CF_IDS = ("ifrs-full_CashFlowsFromUsedInOperatingActivities",)

ACCT_CAPEX = (
    "유형자산의취득", "유형자산의 취득",
    "유형자산취득", "유형자산 취득",
    "유형자산및무형자산의취득", "유형자산및무형자산의 취득",
    "유형자산의 증가",
    "건설중인자산의 증가",
)
ACCT_CAPEX_IDS = (
    "ifrs-full_PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities",
    "dart_PurchaseOfPropertyPlantAndEquipment",
)

ACCT_TOTAL_ASSETS = ("자산총계",)
ACCT_TOTAL_ASSETS_IDS = ("ifrs-full_Assets",)


# ----------------------------------------------------------------------
# raw item picker / 3년치 추출
# ----------------------------------------------------------------------


def _pick_account(
    items: list[dict[str, Any]],
    *,
    sj_div: str,
    names: tuple[str, ...],
    account_ids: tuple[str, ...] = (),
) -> dict[str, Any] | None:
    """sj_div + account_id (1차) / account_nm (2차) 매칭.

    DART 응답의 sj_div: BS(재무상태표) / IS(손익계산서) / CIS(포괄손익) / CF(현금흐름).
    """
    norm_ids = {a.strip() for a in account_ids if a}
    norm_names = {n.strip() for n in names}

    # 1차: account_id 정확 매칭
    if norm_ids:
        for it in items:
            if (it.get("sj_div") or "").strip() != sj_div:
                continue
            aid = (it.get("account_id") or "").strip()
            if aid and aid in norm_ids:
                return it

    # 2차: account_nm 정확 매칭
    for it in items:
        if (it.get("sj_div") or "").strip() != sj_div:
            continue
        nm = (it.get("account_nm") or "").strip()
        if nm in norm_names:
            return it
    return None


def _extract_3y(
    item: dict[str, Any] | None,
) -> tuple[float | None, float | None, float | None]:
    """단일 DART row 의 (전전기, 전기, 당기) 3개 값 추출. None-safe."""
    if not item:
        return None, None, None

    def _to_float(v: Any) -> float | None:
        if v is None or v == "":
            return None
        try:
            return float(str(v).replace(",", ""))
        except (TypeError, ValueError):
            return None

    pp = _to_float(item.get("bfefrmtrm_amount"))
    p = _to_float(item.get("frmtrm_amount"))
    t = _to_float(item.get("thstrm_amount"))
    return pp, p, t


def _safe_div(num: float | None, den: float | None) -> float | None:
    """0 분모 / None 시 None."""
    if num is None or den is None or den == 0:
        return None
    return num / den


# ----------------------------------------------------------------------
# DART items → FilingMetric / metrics
# ----------------------------------------------------------------------


def build_filings(
    items: list[dict[str, Any]],
    *,
    bsns_year: int,
    filing_datetime: datetime,
    citation: str,
) -> list[FilingMetric]:
    """단일 사업보고서 응답 → 3개 annual FilingMetric (3년치).

    DART fnlttSinglAcntAll 응답은 1 회 호출에 (전전기, 전기, 당기) 3년치를
    포함. fiscal_period 는 ``{year}Y`` 표기. period_end_date 는 12-31 (annual).

    filing_datetime / citation 은 3 년치 공통 (정정 공시 별도 처리 — 호출자
    책임).
    """
    rev = _pick_account(items, sj_div="IS", names=ACCT_REVENUE, account_ids=ACCT_REVENUE_IDS) \
        or _pick_account(items, sj_div="CIS", names=ACCT_REVENUE, account_ids=ACCT_REVENUE_IDS)
    op = _pick_account(items, sj_div="IS", names=ACCT_OPERATING_INCOME, account_ids=ACCT_OPERATING_INCOME_IDS) \
        or _pick_account(items, sj_div="CIS", names=ACCT_OPERATING_INCOME, account_ids=ACCT_OPERATING_INCOME_IDS)
    ni = _pick_account(items, sj_div="IS", names=ACCT_NET_INCOME, account_ids=ACCT_NET_INCOME_IDS) \
        or _pick_account(items, sj_div="CIS", names=ACCT_NET_INCOME, account_ids=ACCT_NET_INCOME_IDS)
    assets = _pick_account(items, sj_div="BS", names=ACCT_TOTAL_ASSETS, account_ids=ACCT_TOTAL_ASSETS_IDS)
    eq = _pick_account(items, sj_div="BS", names=ACCT_TOTAL_EQUITY, account_ids=ACCT_TOTAL_EQUITY_IDS)
    liab = _pick_account(items, sj_div="BS", names=ACCT_TOTAL_LIABILITIES, account_ids=ACCT_TOTAL_LIABILITIES_IDS)
    int_exp = _pick_account(items, sj_div="IS", names=ACCT_INTEREST_EXPENSE, account_ids=ACCT_INTEREST_EXPENSE_IDS) \
        or _pick_account(items, sj_div="CIS", names=ACCT_INTEREST_EXPENSE, account_ids=ACCT_INTEREST_EXPENSE_IDS)
    op_cf = _pick_account(items, sj_div="CF", names=ACCT_OPERATING_CF, account_ids=ACCT_OPERATING_CF_IDS)
    capex = _pick_account(items, sj_div="CF", names=ACCT_CAPEX, account_ids=ACCT_CAPEX_IDS)

    series: dict[str, tuple[float | None, float | None, float | None]] = {
        "revenue": _extract_3y(rev),
        "operating_income": _extract_3y(op),
        "net_income": _extract_3y(ni),
        "total_assets": _extract_3y(assets),
        "total_equity": _extract_3y(eq),
        "total_debt": _extract_3y(liab),
        "finance_costs": _extract_3y(int_exp),
        "operating_cash_flow": _extract_3y(op_cf),
        "capex": _extract_3y(capex),
    }

    out: list[FilingMetric] = []
    for offset, idx in ((-2, 0), (-1, 1), (0, 2)):
        year = bsns_year + offset
        out.append(
            FilingMetric(
                fiscal_period=f"{year}Y",
                period_end_date=date(year, 12, 31),
                filing_datetime=filing_datetime,
                kind="annual",
                is_amended=False,
                revenue=series["revenue"][idx],
                operating_income=series["operating_income"][idx],
                net_income=series["net_income"][idx],
                total_assets=series["total_assets"][idx],
                total_equity=series["total_equity"][idx],
                total_debt=series["total_debt"][idx],
                finance_costs=series["finance_costs"][idx],
                operating_cash_flow=series["operating_cash_flow"][idx],
                capex=_capex_normalized(series["capex"][idx]),
                citation=citation,
            )
        )
    return out


def _capex_normalized(v: float | None) -> float | None:
    """CapEx 부호 정규화 — 일부 보고서는 음수, 일부는 양수.

    TickerSnapshot.fcf_recent() = OpCF − CapEx 의 의미를 유지하려면 CapEx 는
    양수 (지출). 음수로 보고된 경우 절댓값 사용.
    """
    if v is None:
        return None
    return abs(v)


def build_metrics_legacy(
    filings: list[FilingMetric], *, tax_rate: float
) -> dict[str, Any]:
    """legacy v3 metrics dict — Stage 3/4/6 의 인용 호환 + audit 보조.

    raw FilingMetric 에서 derived 값 산출. v4 cache 에도 함께 보관 — Rule
    엔진은 FilingMetric API 를 쓰지만 본 metrics dict 는 brief author 의
    빠른 인용용.
    """
    if not filings:
        return {
            "roic_annual": [],
            "fcf_annual": [],
            "revenue_recent": None,
            "fcf_recent": None,
            "debt_to_equity": None,
            "interest_coverage": None,
            "interest_coverage_basis": None,
            "capital_allocation_signals": [],
        }

    def _roic(f: FilingMetric) -> float | None:
        if f.operating_income is None:
            return None
        invested = (f.total_equity or 0) + (f.total_debt or 0)
        if invested <= 0:
            return None
        return (f.operating_income * (1.0 - tax_rate)) / invested

    def _fcf(f: FilingMetric) -> float | None:
        if f.operating_cash_flow is None:
            return None
        return f.operating_cash_flow - (f.capex or 0)

    roic_series = [v for v in (_roic(f) for f in filings) if v is not None]
    fcf_series = [v for v in (_fcf(f) for f in filings) if v is not None]

    latest = filings[-1]
    de = _safe_div(latest.total_debt, latest.total_equity)
    ic = _safe_div(latest.operating_income, latest.finance_costs)

    return {
        "roic_annual": roic_series,
        "fcf_annual": fcf_series,
        "revenue_recent": latest.revenue,
        "fcf_recent": _fcf(latest),
        "debt_to_equity": de,
        "interest_coverage": ic,
        "interest_coverage_basis": None,  # account_id basis 추적은 v5+
        "capital_allocation_signals": [],  # capital_signals_events 에서 derive
    }


# ----------------------------------------------------------------------
# DART 호출 → 단일 ticker 종합
# ----------------------------------------------------------------------


def fetch_filings_for_ticker(
    api_key: str,
    *,
    corp_code: str,
    bsns_year: int,
    citation: CitationPort,
    fs_div: str = _boundary.DART_FS_DIV_CONSOLIDATED,
) -> tuple[list[FilingMetric], str]:
    """단일 ticker 의 annual filings 3년치 + citation. fetch 실패 시 ([], "").

    ``citation`` 은 composition root 가 주입한 CitationPort (G7 포맷) — 어댑터가
    ``_boundary.format_citation`` free fn 을 직접 호출하지 않는다 (Phase 0 seam).
    """
    try:
        items = _boundary.dart_fetch_financial_statements(
            api_key,
            corp_code=corp_code,
            bsns_year=str(bsns_year),
            reprt_code=_boundary.DART_REPRT_CODE_ANNUAL,
            fs_div=fs_div,
        )
    except _boundary.DartUnavailable:
        return [], ""

    if not items:
        return [], ""

    fetched_ts = _boundary.now_iso_kst()
    citation_str = citation.format(
        "DART",
        fetched_ts,
        {
            "corp_code": corp_code,
            "bsns_year": str(bsns_year),
            "reprt_code": _boundary.DART_REPRT_CODE_ANNUAL,
            "fs_div": fs_div,
            "row_count": len(items),
        },
    )
    filing_datetime = datetime.fromisoformat(fetched_ts)
    filings = build_filings(
        items,
        bsns_year=bsns_year,
        filing_datetime=filing_datetime,
        citation=citation_str,
    )
    return filings, citation_str


def detect_capital_signals_events(
    api_key: str,
    *,
    stock_code: str,
    corp_code: str | None,
    end_date: date,
    citation: CitationPort,
    lookback_months: int = 12,
) -> list[dict[str, Any]]:
    """B-type 공시 lookback → capital allocation signal events list.

    각 event: ``{event_datetime, signal_type, report_nm, rcept_no, citation}``.
    DART rcept_dt 는 date-only — event_datetime 은 23:59:59 KST 로 conservative
    (백테스트 시 익일 시가 평가에서 visible). ``citation`` 은 주입된 CitationPort.
    """
    end_dt = datetime.combine(end_date, datetime.min.time())
    bgn_dt = end_dt.replace(day=1)
    year = bgn_dt.year
    month = bgn_dt.month - lookback_months
    while month <= 0:
        month += 12
        year -= 1
    bgn_dt = bgn_dt.replace(year=year, month=month)

    events: list[dict[str, Any]] = []
    try:
        for item in _boundary.dart_iter_disclosures(
            api_key,
            bgn_de=bgn_dt.strftime("%Y-%m-%d"),
            end_de=end_date.isoformat(),
            pblntf_ty="B",
            corp_code=corp_code,
        ):
            if corp_code is None:
                if (item.get("stock_code") or "").strip() != stock_code:
                    continue

            sig = _classify_signal(item.get("report_nm") or "")
            if sig is None:
                continue

            rcept_dt = (item.get("rcept_dt") or "").strip()
            if len(rcept_dt) != 8:
                continue
            event_dt = datetime(
                int(rcept_dt[:4]), int(rcept_dt[4:6]), int(rcept_dt[6:8]),
                23, 59, 59,
            ).replace(tzinfo=_boundary.KST)
            rcept_no = (item.get("rcept_no") or "").strip()

            events.append(
                {
                    "event_datetime": event_dt.isoformat(timespec="seconds"),
                    "signal_type": sig,
                    "report_nm": item.get("report_nm") or "",
                    "rcept_no": rcept_no,
                    "citation": citation.format(
                        "DART",
                        event_dt.isoformat(timespec="seconds"),
                        {"rcept_no": rcept_no, "type": sig},
                    ),
                }
            )
    except _boundary.DartUnavailable:
        return []
    return events


def _classify_signal(report_nm: str) -> str | None:
    """공시 report_nm → signal_type. 매칭 안 되면 None."""
    if not report_nm:
        return None
    if "자기주식소각" in report_nm or "주식소각" in report_nm or "이익소각" in report_nm:
        return "treasury_share_cancellation"
    if "자기주식취득" in report_nm or "자기주식 취득결정" in report_nm:
        return "treasury_share_purchase"
    if "현금배당" in report_nm:
        return "dividend_payment"
    return None


def determine_bsns_year(end_date: date) -> int:
    """end_date 기준 가장 최근에 발표 가능성 있는 사업보고서의 ``bsns_year``.

    한국 사업보고서는 (회계연도 +3개월) 까지 제출 의무. 즉:
    - 3월 말 이전: 작년의 사업보고서 미발표 → 전년도 사용
    - 4월 이후: 작년 사업보고서 가시 → 작년 사용
    실제 미발표 종목은 fetch 시 status='013' → 빈 list 로 graceful.
    """
    cutoff = end_date.replace(month=4, day=1)
    if end_date < cutoff:
        return end_date.year - 2
    return end_date.year - 1


def filing_age_seconds(filings: list[FilingMetric], now: datetime) -> int:
    """가장 최근 filing 의 age (초). filings 비어있으면 sys.maxsize."""
    if not filings:
        return 10**12
    latest = max(filings, key=lambda f: f.filing_datetime)
    delta: timedelta = now - latest.filing_datetime
    return int(delta.total_seconds())
