"""shared DART disclosure scan — universe/catalyst 의 per-item 매칭 루프 단일화 (catch #3).

3 catalyst detector (treasury / spin_off / activist) + universe ``DartDisclosureFilter``
가 복제하던 *"iterate → stock_code 검증 → keyword group 첫매칭 → keep 필터 → dedup →
yield"* 스켈레톤을 본 generator 로 통합. fetch source 는 ``DisclosureSourcePort`` 로 주입
→ infra/DART import 0 (D-CORE-4 안전). window 계산 / retry(progressive degrade) / warning
문자열 / 도메인 객체 매핑 / G7 citation 은 호출 BC 가 보유 — byte-parity 보존.

screener ``io.dart_adapter.detect_capital_signals_events`` 는 본 primitive 미채택:
dedup 부재 + ``_classify_signal`` 다분기 + corp_code 조건부 stock_code 게이트로 의미가
달라 강제 통합 시 행동 변경 위험 (의도된 제외 — screener/.guidelines/05-boundaries.md 기록).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterator, Mapping, Sequence

from domains._shared.ports.disclosure import DisclosureSourcePort


@dataclass(frozen=True)
class MatchedDisclosure:
    """정규화된 매칭 공시 — 도메인 객체(UniverseEntry/CatalystEvent) 매핑 전 중간표현."""

    item: Mapping[str, Any]
    """raw DART list item — 매핑에서 corp_name / flr_nm 등 부가 필드 접근용."""
    ticker: str
    stock_code: str
    report_nm: str
    rcept_no: str
    rcept_dt: str
    matched_group: str
    """매칭된 keyword group name (단일 group 도 group name 보존 — catalyst_type 등 매핑 키)."""


def scan_disclosures(
    source: DisclosureSourcePort,
    *,
    bgn_de: str,
    end_de: str,
    pblntf_ty: str,
    keyword_groups: Mapping[str, Sequence[str]],
    dedup_key: Callable[[MatchedDisclosure], str],
    keep: Callable[[MatchedDisclosure], bool] | None = None,
    corp_code: str | None = None,
) -> Iterator[MatchedDisclosure]:
    """공시 list 를 매칭/dedup 해 ``MatchedDisclosure`` yield (단일 fetch window).

    순서: stock_code 검증(6자리) → keyword_groups 삽입순 첫매칭 → ``keep`` → dedup.
    모든 술어가 dedup 전 적용되고 dedup key 가 rcept_no 기반 유일이므로 술어 평가 순서는
    출력에 영향 없음 (소비 BC 들의 상이한 내부 순서와 byte-동일). ``keep`` 은 catalyst 의
    universe 게이트 / activist 의 known-funds 필터 같은 BC 전용 술어 주입용 (dedup 전 적용).
    DART 실패(``DartUnavailable``)는 catch 하지 않고 호출 BC 의 try/except 로 전파한다.
    """
    seen: set[str] = set()
    for item in source(
        bgn_de=bgn_de, end_de=end_de, pblntf_ty=pblntf_ty, corp_code=corp_code
    ):
        report_nm = (item.get("report_nm") or "").strip()
        stock_code = (item.get("stock_code") or "").strip()
        if not stock_code or len(stock_code) != 6:
            continue
        matched_group: str | None = None
        for group, keywords in keyword_groups.items():
            if any(k in report_nm for k in keywords):
                matched_group = group
                break
        if matched_group is None:
            continue
        rcept_no = (item.get("rcept_no") or "").strip()
        rcept_dt = (item.get("rcept_dt") or "").strip()
        md = MatchedDisclosure(
            item=item,
            ticker=f"KR:{stock_code}",
            stock_code=stock_code,
            report_nm=report_nm,
            rcept_no=rcept_no,
            rcept_dt=rcept_dt,
            matched_group=matched_group,
        )
        if keep is not None and not keep(md):
            continue
        key = dedup_key(md)
        if key in seen:
            continue
        seen.add(key)
        yield md
