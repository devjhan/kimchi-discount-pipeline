# Universe BC Overview

Stage 1 fan-in collector + per-source attribute enricher. `domains/universe/` 가 self-contained bounded context.

## 4 Anchor

1. **`sources/factory.build_source` 단일 진입점** — 모든 DiscoverySource 인스턴스화는 본 함수 통과
2. **`enrichers/factory.build_enricher` + `applies_to` 화이트리스트** — 각 enricher 는 매칭 source_category 명시
3. **`_boundary.py` 단일 외부 게이트** — infra 직접 import 금지
4. **AsOfClock 공유 single source** — `domains._shared.time.clock`

## 패키지 구조

```
domains/universe/
  __init__.py
  _boundary.py             # 외부 의존 단일 게이트
  domain/
    entry.py               # UniverseEntry (frozen)
    result.py              # UniverseResult
    enriched.py            # EnrichedEntry
  sources/                 # DiscoverySource plugins
    base.py / registry.py / factory.py
    literal_list.py / holding_company.py / dart_disclosure_filter.py / preferred_share_pair_seed.py
  enrichers/               # Enricher plugins
    base.py / registry.py / factory.py
    nav_discount.py / spread_zscore.py
  audit/                   # G6 / G7 / G14 invariants + JSONL log
  application/
    build_universe.py      # orchestrator (fan-in → dedup → exclusions → enrichment)
  config/                  # self-contained YAML
  main.py                  # CLI entry
```

## 외부 연결점

| 방향 | 인터페이스 | 위치 |
|---|---|---|
| 입력 (config) | `config/*.yaml` (sources, enrichers, subsidiaries, ...) | 패키지 내부 self-contained |
| 입력 (env) | `DART_API_KEY`, `KIS_APP_KEY` 등 | `.env` via `_boundary.load_env()` |
| 입력 (date) | KST `AsOfClock` | `domains/_shared/time/clock.py` |
| 출력 | `$TRAIL_TODAY/01-universe.json` (envelope `investment-stage1-universe-v1`) | `_boundary.resolve_path("trail_today")` |
| 출력 (audit log) | `$AUDIT_DIR/violations/universe/{date}.jsonl` | JSONL append |
| 출력 (handoff) | stdout 1줄 stage handoff summary | `_boundary.emit_summary` |

## DDD 규약

- 다른 universe 모듈은 `infrastructure.*` / `os.environ` 직접 사용 금지 → `_boundary.py` 통과
- 다른 도메인 (`domains.screener`, `domains.alpha_factory`) import 금지
- 예외: `domains._shared.*` (clock/calendar/ports/adapters)
- 패키지 외부는 산출 파일 + envelope schema 만 인용, 내부 객체 import 금지

## 검증

```bash
grep -rn "from infrastructure\|import infrastructure" domains/universe/ | grep -v _boundary.py
# 결과 0 줄

grep -rn "from domains\." domains/universe/ | grep -v "domains.universe\|domains._shared"
# 결과 0 줄
```
