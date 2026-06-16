"""segment semantic 멤버십 calibration 측정 하네스 (Task 6 / 핸드오프 §6 Task F).

이미 빌드된 ``telemetry/segments/vectors.sqlite`` 를 읽어, concept(seed-centroid)와 각 ticker
사이의 cosine 분포를 측정한다. 지주 seed군(holdco)과 운영사(negative control)가 분리되는지,
top_k·floor 임계를 *실측* 으로 정할 근거를 제공한다 (G8 — 임의 하향 금지, 분리 안 되면 정직
보고). 멤버십 판정 자체는 SegmentResolver 가 소유하며, 본 하네스는 read-only 측정만 한다.

사용:
    python -m applications.verify_segment_calibration
    python -m applications.verify_segment_calibration --concept holdco_value_trap

G21: secret 미노출. 벡터/유사도는 공개 공시 임베딩에서 파생된 측정치라 출력 가능.
"""
from __future__ import annotations

import argparse
import sys

from domains._shared.segment_registry.concepts import ConceptRegistry
from domains.universe import _boundary

# calibration 분류 — 핸드오프 watchlist + 운영사 negative control (seed 는 concept.seed_tickers).
_HOLDCO = {
    "KR:003550": "(주)LG",
    "KR:034730": "SK(주)",
    "KR:078930": "GS(주)",
    "KR:028260": "삼성물산",
}
_OPERATING = {
    "KR:090430": "아모레퍼시픽",
    "KR:000270": "기아",
    "KR:005930": "삼성전자",
    "KR:005380": "현대차",
    "KR:000660": "SK하이닉스",
    "KR:051910": "LG화학",
    "KR:066570": "LG전자",
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="applications.verify_segment_calibration")
    parser.add_argument("--concept", default="holdco_value_trap")
    args = parser.parse_args(argv)

    store = _boundary.vector_index()
    concept_id = args.concept
    reg = ConceptRegistry(root=_boundary.concepts_root())
    concept = reg.load_latest(concept_id)
    if concept is None:
        print(f"concept {concept_id!r} 미등록 — calibration 불가")
        return 1
    print(f"concept={concept_id} (seed_tickers={list(concept.seed_tickers)})")
    if store.get_vector("concept", concept_id) is None:
        print("concept 벡터 미적재 — 먼저 segment_index_main 빌드 필요")
        return 2

    rows: list[tuple[str, str, str, float | None]] = []  # (cohort, ticker, name, cosine)
    for ticker, name in _HOLDCO.items():
        rows.append(("HOLDCO", ticker, name, store.cosine(ticker, concept_id)))
    for ticker, name in _OPERATING.items():
        rows.append(("OPER  ", ticker, name, store.cosine(ticker, concept_id)))

    measured = [(c, t, n, s) for (c, t, n, s) in rows if s is not None]
    measured.sort(key=lambda r: r[3], reverse=True)

    print("\n=== cosine vs concept (내림차순) ===")
    for cohort, ticker, name, score in measured:
        print(f"  {score:+.4f}  [{cohort}]  {ticker}  {name}")

    holdco_scores = [s for (c, _, _, s) in measured if c == "HOLDCO"]
    oper_scores = [s for (c, _, _, s) in measured if c == "OPER  "]

    print("\n=== 분리 통계 ===")
    if holdco_scores:
        print(f"  HOLDCO: n={len(holdco_scores)} min={min(holdco_scores):.4f} "
              f"max={max(holdco_scores):.4f} mean={sum(holdco_scores)/len(holdco_scores):.4f}")
    if oper_scores:
        print(f"  OPER  : n={len(oper_scores)} min={min(oper_scores):.4f} "
              f"max={max(oper_scores):.4f} mean={sum(oper_scores)/len(oper_scores):.4f}")
    if holdco_scores and oper_scores:
        margin = min(holdco_scores) - max(oper_scores)
        print(f"  분리 마진 (min(HOLDCO) - max(OPER)) = {margin:+.4f} "
              f"→ {'SEPARABLE' if margin > 0 else 'OVERLAP (분리 실패)'}")
        if margin > 0:
            floor = (min(holdco_scores) + max(oper_scores)) / 2
            print(f"  제안 floor(중간값) = {floor:.4f}  (top_k = HOLDCO 수 = {len(holdco_scores)})")

    print("\n=== top_k (concept 기준 상위 12) ===")
    for rank, (ticker, score) in enumerate(store.top_k(concept_id, 12), 1):
        name = _HOLDCO.get(ticker) or _OPERATING.get(ticker) or "?"
        print(f"  #{rank:<2} {score:+.4f}  {ticker}  {name}")

    close = getattr(store, "close", None)
    if callable(close):
        close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
