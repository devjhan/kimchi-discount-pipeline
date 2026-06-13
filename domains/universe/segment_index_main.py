"""segment 벡터 인덱스 build 오케스트레이션 entry (Task 9).

usage:
    python -m domains.universe.segment_index_main --date 2026-05-17
    python -m domains.universe.segment_index_main --dry-run
    python -m domains.universe.segment_index_main --texts-file curated_texts.json

역할: 그날 universe trail(``01-universe.json``)의 종목 + concept 선언을 임베딩해
telemetry sqlite-vec 저장소(``telemetry/segments/vectors.sqlite``)에 적재하고, rule-based
selector 가 쓰는 scalar 선택 속성(source_category / market_cap_krw / nav_discount_pct
등)을 함께 materialize 한다. 순수 build 로직은 ``segment_registry.build.build_segment_index``
(주입형 ports) 이고, 본 모듈은 그 ports 를 universe ``_boundary`` 로 구성하는 composition
root 다.

graceful (G8/G11):
- EMBEDDING_API_KEY 부재 / dry-run → 임베딩 skip, scalar 만 적재 (rule-based 선택은 계속).
- universe trail 부재 → 빈 종목 + concept anchor 만 (warning).
- per-ticker 임베딩 텍스트는 수기 큐레이션(``--texts-file``) 우선. DART 사업보고서 "사업의
  내용" 본문 source 는 ``_boundary`` 가 CompositeTickerTextSource 로 주입(Task 8).
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date as _date
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from domains._shared.adapters.ticker_text import (
    CompositeTickerTextSource,
    ManualTickerTextSource,
)
from domains._shared.segment_registry.build import build_segment_index
from domains._shared.segment_registry.concepts import ConceptDeclaration, ConceptRegistry
from domains.universe import _boundary

STAGE_NAME = "segment-index-build"
_UNIVERSE_TRAIL_FILENAME = "01-universe.json"


def _parse_date(s: str | None) -> _date:
    if s:
        return datetime.strptime(s, "%Y-%m-%d").date()
    return _boundary.now_kst().date()


def _scalars_from_entry(entry: Mapping[str, Any]) -> dict[str, Any]:
    """universe entry → 화이트리스트 선택 속성만 추출 (attributes.SELECTION_ATTRIBUTES).

    부재 속성은 생략 — 없는 값을 날조하지 않는다 (G8). enrichment 파생값(nav_discount_pct
    / spread_zscore)은 enrichments dict 에서, 규모/시장 메타는 metadata 에서 best-effort.
    """
    out: dict[str, Any] = {}
    sc = entry.get("source_category")
    if isinstance(sc, str) and sc:
        out["source_category"] = sc
    meta = entry.get("metadata") or {}
    if isinstance(meta, Mapping):
        for key in ("market_cap_krw", "avg_daily_value_krw", "listing_market"):
            v = meta.get(key)
            if v is not None:
                out[key] = v
    enr = entry.get("enrichments") or {}
    if isinstance(enr, Mapping):
        nav = enr.get("nav_discount") or {}
        if isinstance(nav, Mapping) and nav.get("discount_pct") is not None:
            out["nav_discount_pct"] = nav["discount_pct"]
        spread = enr.get("spread_zscore") or {}
        if isinstance(spread, Mapping):
            for cand in ("spread_zscore", "zscore"):
                if spread.get(cand) is not None:
                    out["spread_zscore"] = spread[cand]
                    break
    return out


def collect_universe_rows(
    universe_path: Path,
) -> tuple[list[str], dict[str, dict[str, Any]], list[str]]:
    """universe trail JSON → (tickers, scalars_by_ticker, warnings).

    trail 부재/손상 → 빈 결과 + warning (concept anchor 만 빌드, G8 graceful).
    """
    warnings: list[str] = []
    if not universe_path.exists():
        warnings.append(f"universe trail 부재: {universe_path} — 종목 0 (concept anchor 만)")
        return [], {}, warnings
    try:
        with universe_path.open("r", encoding="utf-8") as f:
            payload = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        warnings.append(f"universe trail 로드 실패: {exc} — 종목 0")
        return [], {}, warnings

    entries = payload.get("entries") or []
    tickers: list[str] = []
    scalars: dict[str, dict[str, Any]] = {}
    for entry in entries:
        if not isinstance(entry, Mapping):
            continue
        ticker = entry.get("ticker")
        if not isinstance(ticker, str) or not ticker:
            continue
        tickers.append(ticker)
        scalars[ticker] = _scalars_from_entry(entry)
    return tickers, scalars, warnings


def _load_texts_file(path: str | None) -> dict[str, str]:
    """``--texts-file`` (ticker→임베딩텍스트 JSON) 로드. 부재/손상 → 빈 dict."""
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        return {}
    try:
        with p.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, Mapping):
        return {}
    return {str(k): str(v) for k, v in data.items() if v}


def _load_concepts() -> list[ConceptDeclaration]:
    """ConceptRegistry 의 모든 concept 최신 버전 로드 (손상 → ConceptSchemaError 전파)."""
    reg = ConceptRegistry(root=_boundary.concepts_root())
    out: list[ConceptDeclaration] = []
    for cid in reg.list_concepts():
        c = reg.load_latest(cid)
        if c is not None:
            out.append(c)
    return out


def _build_text_source(manual_texts: Mapping[str, str], env: Mapping[str, str]) -> Any:
    """임베딩 텍스트 source 구성. 수기 큐레이션 우선, DART 사업의 내용 본문 fallback (Task 8).

    DART 본문 source 는 vendor 의존이라 ``_boundary.ticker_text_source(env)`` 가 구성한다.
    키 부재/구성 실패 → 수기 source 만 사용 (graceful).
    """
    sources: list[Any] = [ManualTickerTextSource(texts=dict(manual_texts))]
    factory = getattr(_boundary, "ticker_text_source", None)
    if callable(factory):
        try:
            dart_source = factory(dict(env))
            if dart_source is not None:
                sources.append(dart_source)
        except Exception:  # noqa: BLE001 — DART source 구성 실패 → 수기만 (graceful)
            pass
    return CompositeTickerTextSource(sources=sources)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="domains.universe.segment_index_main",
        description="Segment 벡터 인덱스 build — universe + concept 임베딩/scalar 적재.",
    )
    parser.add_argument("--date", help="YYYY-MM-DD (KST). 기본: 오늘 거래일.")
    parser.add_argument(
        "--trail-dir", default=None,
        help="universe trail dir override. 기본: $TRAIL_TODAY / operations/{거래일}.",
    )
    parser.add_argument(
        "--texts-file", default=None,
        help="ticker→임베딩 텍스트 수기 큐레이션 JSON (선택). DART 본문 source 보다 우선.",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="임베딩 호출 skip (scalar 만 적재). 인덱스 파일은 갱신됨.",
    )
    args = parser.parse_args(argv)

    target_date = _parse_date(args.date)
    date_iso = target_date.isoformat()
    trail_dir = (
        Path(args.trail_dir) if args.trail_dir else _boundary.resolve_trail_dir(date_iso)
    )
    universe_path = trail_dir / _UNIVERSE_TRAIL_FILENAME

    env: dict[str, str] = {} if args.dry_run else _boundary.load_env()

    tickers, scalars_by_ticker, warnings = collect_universe_rows(universe_path)
    text_source = _build_text_source(_load_texts_file(args.texts_file), env)
    concepts = _load_concepts()

    embedding = _boundary.embedding_port(env, dry_run=args.dry_run)
    vector_index = _boundary.vector_index()
    try:
        report = build_segment_index(
            tickers=tickers,
            text_for=text_source.text_for,
            scalars_for=lambda t: scalars_by_ticker.get(t, {}),
            concepts=concepts,
            embedding=embedding,
            vector_index=vector_index,
            now_iso=_boundary.now_iso_kst(),
        )
    finally:
        close = getattr(vector_index, "close", None)
        if callable(close):
            close()

    all_warnings = [*warnings, *report.warnings]
    _boundary.emit_summary(
        STAGE_NAME,
        {
            "date": date_iso,
            "model": report.model_id,
            "embedded_tickers": report.embedded_tickers,
            "embedded_concepts": report.embedded_concepts,
            "skipped_fresh": report.skipped_fresh,
            "scalars_written": report.scalars_written,
            "embedding_skipped": report.embedding_skipped,
            "warnings": len(all_warnings),
            "mode": "dry-run" if args.dry_run else "live",
        },
        _boundary.vector_store_path(),
    )
    for w in all_warnings:
        print(f"[{STAGE_NAME}] WARN: {_boundary.secret_safe_log(w, env)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
