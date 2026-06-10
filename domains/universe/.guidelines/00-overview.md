# universe — DDD Modular Monolith Overview

투자 파이프라인 Stage 1 의 fan-in collector + per-source attribute enricher.
`domains/universe/` 패키지가 self-contained bounded context.

## 4 Anchor (변경 시 도메인 안정성 영향)

1. **`sources/factory.build_source` 단일 진입점** — 모든 DiscoverySource 인스턴스화는 본 함수 통과. 직접 `LiteralListSource(...)` 생성 시 registry 외 source type 우회 통로가 열린다. test 코드도 build_source 사용 권장 (단, ABC 구현 검증 목적의 직접 instantiate 는 허용 — `domains/universe/tests/unit/test_universe_sources.py` 참조).

2. **`enrichers/factory.build_enricher` + `applies_to` 화이트리스트** — 모든 Enricher 인스턴스화는 본 함수 통과. 각 enricher 는 `applies_to: frozenset[str]` 로 매칭 source_category 명시 — cross-attach 금지 (예: NavDiscountEnricher 가 activist_filing entry 에 attach 시 audit invariant `enricher_orphan` warning). 신규 source_category 추가는 enricher 의 applies_to 확장 PR 별도 필요.

3. **`_boundary.py` 단일 외부 게이트** — 다른 universe 모듈이 `infrastructure.*` (utils / dart.client / kis.client / yahoo.client) 또는 `from_alias`, `os.environ` 직접 호출 시 컨벤션 위반. 외부 의존 추가는 boundary 갱신 + 본 디렉토리 + README cross-ref 동시 PR. 검증: `grep -rn "from infrastructure" domains/universe/ --include="*.py"` 결과는 `_boundary.py` 1 파일만 (`03-boundaries.md` 참조).

4. **AsOfClock 공유 single source (`domains._shared.time.clock`)** — universe 도메인은 자체 clock 클래스 정의 금지. screener / universe / macro (Run 7+) 모두 동일 `AsOfClock` 인스턴스 비교 / 정렬 / 해시 일관성을 위해 `domains/_shared/time/clock.py` 한 곳에서만 정의. DiscoveryContext / EnrichContext 가 본 clock 을 받아 source / enricher 로 전파.

## 패키지 핵심 객체 (Run 6 시점)

### domain/ — frozen value objects
- `entry.py` `UniverseEntry` — 단일 종목 후보 (ticker / name / source_category / inclusion_reason / fetched_at / source_citation / metadata)
- `enriched.py` `EnrichedEntry` — UniverseEntry top-level 필드 + `enrichments: Mapping[name, attributes]` + `enrichment_citations` + `enrichment_warnings` + `enrichment_skips`. base 필드는 downstream readers 호환 보장.
- `enriched.py` `EnrichmentResult` — 단일 enricher 의 enrich() 산출 (attributes / citations / warnings / skip_reason)
- `result.py` `UniverseResult` — build_universe() 의 산출 묶음 (entries / warnings / skipped_sources / stats)

### sources/ — DiscoverySource plugins (Run 2~5)
- `base.py` `DiscoverySource` ABC + `DiscoveryContext` (clock + env) + `SourceResult` (entries / warnings / degraded)
- `registry.py` `SOURCE_TYPES` dict + `@register_source(name)` decorator
- `factory.py` `build_source(spec)` + `build_sources(specs)` — sources.yaml dispatch
- 5 concrete sources: `literal_list` / `holding_company` / `dart_disclosure_filter` (treasury/spin_off_or_merger/activist 3 인스턴스) / `preferred_share_pair_seed`

### enrichers/ — Enricher plugins (Run 5)
- `base.py` `Enricher` ABC + `EnrichContext` (clock + env + allow_yahoo)
- `registry.py` `ENRICHER_TYPES` dict + `@register_enricher(name)` decorator
- `factory.py` `build_enricher(spec)` + `build_enrichers(specs)` — enrichers.yaml dispatch
- 2 concrete enrichers: `nav_discount` (holding_company 전용) / `spread_zscore` (preferred_share_pair 전용)

### application/ — orchestrator
- `build_universe.py` — fan-in discovery → dedup → exclusions → enrichment 의 단일 함수

### audit/ — invariant checks + JSONL log (Run 4/6)
- `violation.py` `GuardViolation` — invariant 위반 1건의 frozen 표현
- `log.py` `ViolationLog` — `$AUDIT_DIR/universe-violations/{date}.jsonl` append-only
- `citation.py` G7 정규식 (`CITATION_RE`) + `is_valid_citation` + `filter_valid_citations`
- `invariants.py` `validate_g7_citations` + `validate_enricher_applies_to` — main.py 가 build 후 호출

### config/ — self-contained YAML (Run 2~5)
- `sources.yaml` — 6 source entry (1 literal_list + 1 holding_company + 3 dart_disclosure_filter + 1 preferred_share_pair_seed)
- `enrichers.yaml` — 2 enricher entry
- `manual_additions.yaml` / `exclusions.yaml` / `subsidiaries.yaml` / `preferred_pairs.yaml` — sub-config (items_ref / subsidiaries_map_ref / pairs_ref 외부화)

### main.py — CLI entry
- `--date` / `--dry-run` / `--trail-dir` / `--allow-yahoo-fallback`
- exit 0 / 2 (blocking violation 시 2)

## 산출 / 외부 연결점

- 산출: `$TRAIL_TODAY/01-universe.json` (envelope schema `investment-stage1-universe-v1`)
- audit log: `$AUDIT_DIR/universe-violations/{date}.jsonl` (Run 4+)
- handoff: stdout 1줄 stage handoff summary (`[stage1-universe] ... -> path`)
- 외부 도메인 호출: 없음 — universe 는 입력 단계, 다음 stage (screener / catalyst_scan / brief_gate) 가 본 산출물 read
- 외부 의존 (anti-corruption layer 통과): DART (corp index / disclosures / preferred pairs parser) / KIS (current price / daily ohlcv) / Yahoo (fallback ohlcv) / topology aliases

## envelope 호환 보장

`01-universe.json` 의 envelope 구조 — legacy stage1 helper (삭제됨) 와 isomorphic:

> 옛 산출 모듈: `domains.alpha_factory.universe` (Run 4 시점 삭제). envelope schema
> `investment-stage1-universe-v1` 의 모든 top-level / entry 필드 보존 → downstream
> (catalyst_scan, screener.io.universe_loader, brief_gate) 호환.

```jsonc
{
  "schema": "investment-stage1-universe-v1",
  "generated_at": "ISO 8601 KST",
  "date": "YYYY-MM-DD",
  "config_path": "absolute path to sources.yaml",
  "config_version": int,
  "stats": {
    "total": int,
    "by_source_category": {category: count},
    "excluded": int,
    "dry_run": bool,
    "degraded_sources": [name],         // 있을 때만
    "enriched_by": {name: count}        // 있을 때만 (Run 5+)
  },
  "entries": [
    {
      // UniverseEntry base 필드 (downstream readers 호환)
      "ticker": "KR:003550",
      "name": "(주)LG",
      "source_category": "holding_company",
      "inclusion_reason": "...",
      "fetched_at": "ISO 8601 KST",
      "source_citation": "user@ts=v",
      "metadata": {...},
      // EnrichedEntry 추가 필드 (Run 5+, opt-in)
      "enrichments": {"nav_discount": {nav_estimate, discount_pct, ...}},
      "enrichment_citations": ["KIS@ts={...}"],
      "enrichment_warnings": [...],
      "enrichment_skips": {"spread_zscore": "reason"}
    }
  ],
  "warnings": [...],
  "skipped_sources": [{"source": name, "reason": str}]
}
```
