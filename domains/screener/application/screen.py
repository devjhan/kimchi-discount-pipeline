"""단일 시점 스크리닝 orchestrator — universe × Rule 트리 → ScreenVerdict.

흐름:
1. RuleFactory.build_strategy(strategy, profiles, hard_guards, tax_rate) → rule
2. for entry in universe:
   - cache.get_snapshot(ticker, name, clock)
   - cache miss && fetch 가능 → dart_adapter 호출 + cache.write_atomic + re-read
   - snapshot None → ScreenVerdict(verdict='unknown')
   - snapshot OK → rule.evaluate(snapshot) → ScreenVerdict(pass|fail + reasons)
3. ScreenResult 반환

본 모듈은 fetch loop / cache 통합 / Rule 평가의 단일 entry point. grace
fallback / signals_only refetch 는 후속 PR 에서 확장.
"""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field, replace
from typing import Callable

from domains.screener.domain.verdict import RuleResult, ScreenVerdict
from domains.screener.io import dart_adapter as _adapter
from domains.screener.io.capital_signals_cache import (
    filter_visible_signals,
    merge_signal_events,
)
from domains.screener.io.financial_cache import LiveFinancialCache
from domains.screener.io.universe_loader import UniverseEntry
from domains.screener.rules.base import Rule
from domains._shared.ports.citation import CitationPort
from domains._shared.profile_registry.schema import EnrichCutoffProfile
from domains._shared.time.clock import AsOfClock


@dataclass(frozen=True)
class ScreenResult:
    """단일 run 의 산출 — trail_writer 에 그대로 전달."""

    verdicts: tuple[ScreenVerdict, ...]
    warnings: tuple[str, ...]
    stats: dict[str, int] = field(default_factory=dict)


def run_screen(
    *,
    rule_for: Callable[[str], Rule | None],
    profile_for: Callable[[str], EnrichCutoffProfile | None],
    universe: tuple[UniverseEntry, ...],
    cache: LiveFinancialCache,
    clock: AsOfClock,
    tax_rate: float,
    dart_api_key: str | None,
    corp_index: dict[str, str],
    citation: CitationPort,
    dry_run: bool = False,
) -> ScreenResult:
    """전체 universe 평가. dry_run=True 면 fetch skip, 모든 cache miss = unknown.

    정책/메커니즘 분리: 본 함수는 룰을 빌드하지 않고 ``rule_for(ticker)`` /
    ``profile_for(ticker)`` closure 로부터 종목별 Rule + Profile 을 주입받아
    기계적으로 평가한다 (registry I/O 는 closure 내부 = main.py 책임, 단위테스트는
    stub closure 주입). ``rule_for`` 가 ``None`` 반환 → 불량 cutoff_rules → caution.

    ``citation`` (CitationPort) 은 fetch 경로(``_refetch_into_cache`` → dart_adapter)
    에서만 쓰이는 G7 포맷 어댑터 — ``dart_api_key`` 와 같은 fetch-path 주입 의존이다
    (dry_run / api_key=None 이면 미호출).
    """
    verdicts: list[ScreenVerdict] = []
    warnings: list[str] = []
    stats = {"total": 0, "pass": 0, "fail": 0, "caution": 0, "unknown": 0, "fetched": 0}

    bsns_year = _adapter.determine_bsns_year(clock.trading_date)
    end_date = clock.trading_date
    now_epoch = int(time.time())

    for entry in universe:
        stats["total"] += 1
        snapshot = cache.get_snapshot(entry.ticker, entry.name, clock)

        if snapshot is None and not dry_run and dart_api_key:
            ok = _refetch_into_cache(
                api_key=dart_api_key,
                cache=cache,
                entry=entry,
                corp_index=corp_index,
                bsns_year=bsns_year,
                end_date=end_date,
                tax_rate=tax_rate,
                now_epoch=now_epoch,
                warnings=warnings,
                citation=citation,
            )
            if ok:
                stats["fetched"] += 1
                snapshot = cache.get_snapshot(entry.ticker, entry.name, clock)

        if snapshot is None:
            verdicts.append(
                ScreenVerdict(
                    ticker=entry.ticker,
                    name=entry.name,
                    verdict="unknown",
                    score=0.0,
                    reasons=("cache_miss",),
                    citations=((entry.source_citation,) if entry.source_citation else ()),
                    rule_tree=None,
                )
            )
            stats["unknown"] += 1
            continue

        # Stage 1 enrichments 를 snapshot 에 런타임 주입 (point-in-time — 캐시 미저장).
        # frozen 갱신 idiom. 빈 dict (대다수 종목) 면 주입 skip → 동작 변화 0.
        if entry.enrichments:
            snapshot = replace(snapshot, enrichments=entry.enrichments)

        # Step 4.2 — COMPLETENESS GATE: 정책상 필수 enrichment 누락 → caution
        # (fail-safe, 사람 재검토). 프로파일 없음 → 검사 skip (전환기 default_rule 진행).
        # enrichments 는 enricher name 으로 키잉 (snapshot.enrichments[group] = attributes).
        #
        # 의도된 cross-domain 결합: cutoff(Stage 2)가 자기 절반(cutoff_rules) 외에
        # universe(Stage 1)의 ``required_enrichments`` 도 읽어 "enrich 가 무엇을 했어야
        # 하나"로 입력 완전성을 판단한다. 이는 EnrichCutoffProfile 이 enrich+cutoff 를
        # 한 정책 단위로 묶은 데서 오는 결합 — 위반이 아니라 명시적 게이트다. (F-2)
        # governance/pipeline-overview.md "Completeness Gate" 절 참조.
        profile = profile_for(entry.ticker)
        if profile is not None:
            missing = [
                n
                for n in profile.required_enrichments
                if n not in (snapshot.enrichments or {})
            ]
            if missing:
                verdicts.append(
                    ScreenVerdict(
                        ticker=entry.ticker,
                        name=entry.name,
                        verdict="caution",
                        score=0.0,
                        reasons=(f"missing_required_enrichment: {missing}",),
                        citations=snapshot.all_citations(),  # citations 보유 → 면제 아님
                        rule_tree=None,
                    )
                )
                stats["caution"] += 1
                continue  # 배치 미중단: per-ticker 분기 + continue (unknown 블록과 동형)

        # Step 4.1 C: per-ticker rule. None → 불량 cutoff_rules → caution.
        selected_rule = rule_for(entry.ticker)
        if selected_rule is None:
            verdicts.append(
                ScreenVerdict(
                    ticker=entry.ticker,
                    name=entry.name,
                    verdict="caution",
                    score=0.0,
                    reasons=("invalid_profile_rules",),
                    citations=snapshot.all_citations(),
                    rule_tree=None,
                )
            )
            stats["caution"] += 1
            continue

        rule_result = selected_rule.evaluate(snapshot)
        outcome = "pass" if rule_result.passed else "fail"
        stats[outcome] += 1
        verdicts.append(
            ScreenVerdict(
                ticker=entry.ticker,
                name=entry.name,
                verdict=outcome,  # type: ignore[arg-type]
                score=rule_result.score,
                reasons=rule_result.reasons,
                citations=rule_result.citations,
                rule_tree=rule_result,
            )
        )

    return ScreenResult(
        verdicts=tuple(verdicts), warnings=tuple(warnings), stats=stats
    )


def _refetch_into_cache(
    *,
    api_key: str,
    cache: LiveFinancialCache,
    entry: UniverseEntry,
    corp_index: dict[str, str],
    bsns_year: int,
    end_date,
    tax_rate: float,
    now_epoch: int,
    warnings: list[str],
    citation: CitationPort,
) -> bool:
    """단일 ticker fetch + v4 cache 갱신. 성공 시 True. ``citation`` 주입 (G7 포맷)."""
    stock_code = entry.ticker.split(":", 1)[-1]
    corp_code = corp_index.get(stock_code)
    if not corp_code:
        warnings.append(f"{entry.ticker}: corp_code 없음 — fetch skip")
        return False

    filings, fin_citation = _adapter.fetch_filings_for_ticker(
        api_key, corp_code=corp_code, bsns_year=bsns_year, citation=citation,
    )
    if not filings:
        warnings.append(f"{entry.ticker}: DART filings 빈 응답 — verdict=unknown")
        return False

    new_events = _adapter.detect_capital_signals_events(
        api_key, stock_code=stock_code, corp_code=corp_code, end_date=end_date,
        citation=citation,
    )

    prev = cache.read_raw(entry.ticker) or {}
    prev_events = prev.get("capital_signals_events") or []
    prev_meta = prev.get("_cache_meta") if isinstance(prev.get("_cache_meta"), dict) else None
    merged_events = merge_signal_events(prev_events, new_events)

    citations: list[str] = []
    if entry.source_citation:
        citations.append(entry.source_citation)
    if fin_citation:
        citations.append(fin_citation)
    for ev in new_events:
        cit = ev.get("citation")
        if isinstance(cit, str) and cit:
            citations.append(cit)

    metrics = _adapter.build_metrics_legacy(filings, tax_rate=tax_rate)

    cache.write_atomic(
        entry.ticker,
        name=entry.name,
        corp_code=corp_code,
        bsns_year=str(bsns_year),
        tax_rate=tax_rate,
        filings=filings,
        capital_signals_events=merged_events,
        metrics=metrics,
        citations=citations,
        universe_citation=entry.source_citation,
        now_epoch=now_epoch,
        prev_meta=prev_meta,
    )
    return True


def verdicts_as_json(verdicts: tuple[ScreenVerdict, ...]) -> list[dict]:
    """ScreenVerdict tuple → JSON-serializable list (envelope items 용).

    RuleResult 트리는 frozen tuple 이지만 asdict 가 list 로 평탄화.
    """
    return [asdict(v) for v in verdicts]


def _explain_rule_tree(r: RuleResult, depth: int = 0) -> list[str]:
    """RuleResult 트리를 평탄한 reason 라인 list 로 (디버깅 / 보조 산출용)."""
    out = [f"{'  ' * depth}{r.rule_name} passed={r.passed} score={r.score:.3f}"]
    for c in r.children:
        out.extend(_explain_rule_tree(c, depth + 1))
    return out
