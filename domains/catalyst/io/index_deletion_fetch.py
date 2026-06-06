"""Index deletion fetch — 구 ``alpha_factory/stage3_index_deletion_fetch.py`` 이전.

KRX/MSCI 지수 리밸런스 (편입제외) 발표를 DART pblntf_ty='I' 키워드 매치로 검출.
구 helper 는 중간 JSON (``03-index-deletion.json``) 을 디스크에 떨궜으나, 본 모듈은
``IndexDeletionEntry`` list 를 in-memory 로 반환 — index_deletion detector 가 직접
소비 (중간 파일 제거). DART 접근은 ``_boundary`` 경유.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from domains.catalyst import _boundary

# 편입제외 / 지수 변경 키워드 (KRX 거래소공시 deterministic 매치)
KEYWORDS_DELETION = (
    "편입제외",
    "구성종목변경",
    "구성종목 변경",
    "지수변경",
    "정기변경",
    "수시변경",
)
# 지수 명 키워드 — 매치 시 index_name 추정
INDEX_NAME_HINTS = (
    ("KOSPI200", "KOSPI200"),
    ("코스피200", "KOSPI200"),
    ("코스피 200", "KOSPI200"),
    ("KOSDAQ150", "KOSDAQ150"),
    ("코스닥150", "KOSDAQ150"),
    ("KOSPI", "KOSPI"),
    ("KOSDAQ", "KOSDAQ"),
    ("MSCI", "MSCI"),
    ("FTSE", "FTSE"),
)


@dataclass
class IndexDeletionEntry:
    ticker: str
    name: str
    index_name: str
    rcept_no: str
    rcept_dt: str
    report_nm: str
    source_citation: str
    metadata: dict[str, Any] = field(default_factory=dict)


def _infer_index_name(text: str) -> str:
    for hint, label in INDEX_NAME_HINTS:
        if hint in text:
            return label
    return "unknown_index"


def discover_index_deletions(
    env: dict[str, str],
    *,
    end_date: str,
    lookback_days: int,
    fetched_at: str,
) -> tuple[list[IndexDeletionEntry], list[str]]:
    """DART pblntf_ty='I' lookback → keyword 매치 → entries (+ warnings)."""
    warnings: list[str] = []
    if not _boundary.dart_has_key(env):
        warnings.append("DART_API_KEY missing → index_deletion fetch skipped")
        return [], warnings

    api_key = env["DART_API_KEY"]
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    bgn_dt = end_dt - timedelta(days=lookback_days)

    entries: list[IndexDeletionEntry] = []
    seen: set[str] = set()
    try:
        for item in _boundary.dart_iter_disclosures(
            api_key,
            bgn_de=bgn_dt.strftime("%Y-%m-%d"),
            end_de=end_date,
            pblntf_ty="I",
        ):
            report_nm = (item.get("report_nm") or "").strip()
            if not any(k in report_nm for k in KEYWORDS_DELETION):
                continue
            if not any(h[0] in report_nm for h in INDEX_NAME_HINTS):
                # 지수 명 hint 없는 일반 거래소공시 skip (false positive 차단)
                continue
            stock_code = (item.get("stock_code") or "").strip()
            corp_name = (item.get("corp_name") or "").strip()
            rcept_no = (item.get("rcept_no") or "").strip()
            rcept_dt = (item.get("rcept_dt") or "").strip()
            if not stock_code or len(stock_code) != 6 or not stock_code.isdigit():
                continue
            ticker = f"KR:{stock_code}"
            dedup = f"{ticker}|{rcept_no}"
            if dedup in seen:
                continue
            seen.add(dedup)
            index_name = _infer_index_name(report_nm)
            entries.append(
                IndexDeletionEntry(
                    ticker=ticker,
                    name=corp_name,
                    index_name=index_name,
                    rcept_no=rcept_no,
                    rcept_dt=rcept_dt,
                    report_nm=report_nm,
                    source_citation=_boundary.format_citation(
                        "DART",
                        rcept_dt,
                        {"rcept_no": rcept_no, "type": "index_deletion", "index": index_name},
                    ),
                    metadata={"fetched_at": fetched_at, "lookback_days": lookback_days},
                )
            )
    except _boundary.DartUnavailable as exc:
        warnings.append(f"DART index_deletion fetch fail: {exc}")
    return entries, warnings
