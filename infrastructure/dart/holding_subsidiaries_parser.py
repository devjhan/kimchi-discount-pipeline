"""
infrastructure/dart/holding_subsidiaries_parser.py — 지주사 자회사 출자현황
자동 parse (DART OpenAPI 본구현).

DART 사업보고서 주요정보 endpoint `otrCprInvstmntSttus.json` (타법인 출자현황)
을 호출해 회사명 + 지분율을 추출하고, corpCode.xml index 의 회사명 ↔
stock_code 매핑으로 ticker 까지 자동 결정. ticker 결정 실패 시 manual_ssot
fallback 권장 (confidence 필드로 marker).

설계 원칙 (plan D1 결정):
    manual SSOT 우선:
        governance/thresholds.yaml.universe.holding_companies_subsidiaries 가
        single source. 본 parser 의 산출은 보조이며 manual map 과 충돌 시
        manual 값 우선. caller (universe.py) 가 merge 정책 적용.

Hard guards:
    G6:  ownership_pct 등 정량값은 DART 응답 직접 인용 (LLM 추정 금지)
    G7:  caller 가 'DART@<bsns_year>=<corp_code>' 형식으로 citation
    G8:  API key 누락 / DartUnavailable / 빈 응답 → ([], warnings) — raise 금지
    G9b: read-only API 호출만
"""

from __future__ import annotations

from typing import Any

from infrastructure.dart.client import (
    DartUnavailable,
    fetch_other_corp_investment,
)

# 우선주 / 보통주 / 클래스주 suffix — name → base name normalize 용
_PREFERRED_NAME_SUFFIXES = ("우B", "우C", "우", "1우B", "2우B", "3우B")

# DART otrCprInvstmntSttus row → ownership_pct 추출 우선순위
#   trmend_blce_qota_rt 가 가장 최신 (기말 잔액). 없으면 bsis_blce_qota_rt.
_RATE_FIELDS = ("trmend_blce_qota_rt", "bsis_blce_qota_rt")


def _normalize_corp_name(name: str) -> str:
    """corpCode.xml 의 회사명 ↔ DART otrCprInvstmntSttus.inv_prm 매칭 보조.

    - 공백 strip
    - "(주)" / "주식회사" prefix 제거
    - 후행 공백 / 특수문자 제거
    """
    n = name.strip()
    for prefix in ("(주)", "(주식회사)", "주식회사", "(유)", "유한회사"):
        if n.startswith(prefix):
            n = n[len(prefix):].strip()
    return n


def _build_name_to_stock(
    corp_full_index: list[dict[str, str]]
) -> dict[str, list[str]]:
    """corp_full_index → {normalized_name: [stock_code, ...]} mapping.

    같은 normalize 이름이 여러 listed corp 에 매칭될 수 있음 (drop 안 함).
    매칭 ambiguity 는 confidence=auto_parsed_low marker.
    """
    out: dict[str, list[str]] = {}
    for entry in corp_full_index:
        stock = entry.get("stock_code", "").strip()
        name = entry.get("corp_name", "").strip()
        if not stock or not name:
            continue
        key = _normalize_corp_name(name)
        out.setdefault(key, []).append(stock)
    return out


def _parse_pct(value: Any) -> float | None:
    """DART 응답 ratio (예: '12.34' / '12.34%' / '12,345' / '-') → 0.0~1.0 float.

    DART otrCprInvstmntSttus 응답의 비율은 percentage (예 '15.20'). 변환
    실패 / 음수 / 100 초과 시 None.
    """
    if value is None:
        return None
    s = str(value).strip()
    if not s or s in ("-", "—", "N/A", "n/a"):
        return None
    s = s.replace(",", "").replace("%", "").strip()
    try:
        f = float(s)
    except (TypeError, ValueError):
        return None
    if f < 0 or f > 100:
        return None
    return round(f / 100.0, 6)


def parse_subsidiary_table(
    corp_code: str,
    *,
    bsns_year: str,
    env: dict[str, str],
    corp_full_index: list[dict[str, str]] | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    """
    DART otrCprInvstmntSttus.json 호출 → 자회사 entries.

    Args:
        corp_code: 8자리 DART 고유번호 (parent 지주사).
        bsns_year: '2024' 식 4자리 (가장 최근 사업보고서 연도).
        env: dotenv loaded — DART_API_KEY 필요.
        corp_full_index: ticker 자동 결정용. 미제공 시 ticker=None +
                         confidence='auto_parsed_low'.

    Returns:
        entries: [
            {
                "stock_code": "051910" | None,
                "name": "LG화학",
                "ownership_pct": 0.305,
                "listed": True | False,
                "indirect_via": None,
                "confidence": "auto_parsed_high" | "auto_parsed_low",
                "source_citation": "DART@otrCprInvstmntSttus#<corp>#<year>=<inv_prm>",
            },
            ...
        ]
        warnings: list[str]
    """
    warnings: list[str] = []
    api_key = (env or {}).get("DART_API_KEY", "").strip()
    if not api_key:
        warnings.append(
            "DART_API_KEY missing → subsidiary auto-parse skip (manual SSOT 사용)"
        )
        return [], warnings

    try:
        rows = fetch_other_corp_investment(
            api_key, corp_code=corp_code, bsns_year=bsns_year
        )
    except DartUnavailable as exc:
        warnings.append(
            f"DART otrCprInvstmntSttus fetch fail (corp_code={corp_code}, year={bsns_year}): {exc}"
        )
        return [], warnings

    if not rows:
        warnings.append(
            f"DART otrCprInvstmntSttus empty (corp_code={corp_code}, year={bsns_year}) "
            "— 자회사 미보고 또는 사업보고서 미존재"
        )
        return [], warnings

    name_to_stock: dict[str, list[str]] = (
        _build_name_to_stock(corp_full_index) if corp_full_index else {}
    )

    entries: list[dict[str, Any]] = []
    for row in rows:
        inv_prm = (row.get("inv_prm") or "").strip()
        if not inv_prm:
            continue
        ownership = None
        for fld in _RATE_FIELDS:
            ownership = _parse_pct(row.get(fld))
            if ownership is not None:
                break
        normalized = _normalize_corp_name(inv_prm)
        candidate_stocks = name_to_stock.get(normalized, [])

        # ticker 자동 결정
        stock_code: str | None
        listed = False
        confidence = "auto_parsed_low"
        if len(candidate_stocks) == 1:
            stock_code = candidate_stocks[0]
            listed = True
            confidence = "auto_parsed_high"
        elif len(candidate_stocks) > 1:
            # ambiguous — 후보 list 만 metadata 로 보존, 사용자 결정 필요
            stock_code = None
            warnings.append(
                f"name '{inv_prm}' ambiguous — candidates {candidate_stocks}; manual_ssot_required"
            )
        else:
            stock_code = None  # 비상장 / 외국법인 / 매칭 실패

        entries.append(
            {
                "stock_code": stock_code,
                "name": inv_prm,
                "ownership_pct": ownership,
                "listed": listed,
                "indirect_via": None,
                "confidence": confidence,
                "source_citation": (
                    f"DART@otrCprInvstmntSttus#{corp_code}#{bsns_year}={inv_prm}"
                ),
                "candidates": candidate_stocks if not stock_code and candidate_stocks else None,
            }
        )

    return entries, warnings


def merge_with_manual_ssot(
    auto_entries: list[dict[str, Any]],
    manual_entries: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    """
    Manual SSOT 우선 merge — plan D1 정합.

    Rules:
        1. manual_entries 의 모든 entry 는 그대로 유지 (확실한 source).
           confidence='manual_ssot' 추가.
        2. auto_entries 중 manual_entries 의 stock_code 와 일치하지 않는 entry
           만 추가 (manual 우선). confidence 원본 유지.
        3. ticker 결정 실패 (stock_code=None) auto entry 는 '검토 권고' 로
           별도 list 에 보존 → 본 함수는 entries 에 포함하지 않음 (caller 가
           audit_dir 등 별도 채널 처리 권장).

    Returns:
        (merged_entries, warnings) — merged 는 deterministic 순서 (manual first).
    """
    warnings: list[str] = []
    manual_stocks = {
        str(e.get("stock_code", "")).strip()
        for e in manual_entries
        if e.get("stock_code")
    }
    out: list[dict[str, Any]] = []
    for e in manual_entries:
        new = dict(e)
        new.setdefault("confidence", "manual_ssot")
        out.append(new)
    skipped_low_conf = 0
    for e in auto_entries:
        stk = str(e.get("stock_code") or "").strip()
        if not stk:
            skipped_low_conf += 1
            continue
        if stk in manual_stocks:
            continue  # manual 우선
        out.append(e)
    if skipped_low_conf:
        warnings.append(
            f"{skipped_low_conf} auto-parsed entries skipped (ticker 자동 결정 실패). "
            "Inspect with --emit-audit flag if needed."
        )
    return out, warnings


__all__ = [
    "parse_subsidiary_table",
    "merge_with_manual_ssot",
    "_normalize_corp_name",
    "_parse_pct",
]
