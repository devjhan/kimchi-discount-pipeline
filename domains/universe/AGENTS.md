# domains/universe — Stage 1 Universe Bounded Context

투자 파이프라인 Stage 1 의 fan-in collector + per-source attribute enricher.
``domains/screener`` 와 isomorphic 한 DDD modular monolith 패턴.

## 패키지 구조

```
domains/universe/
  __init__.py
  _boundary.py             # 외부 의존 단일 게이트 (infrastructure.* 직접 import 금지)
  domain/
    entry.py               # UniverseEntry (frozen dataclass)
    result.py              # UniverseResult (Run 4)
    enriched.py            # EnrichedEntry (Run 5)
  sources/                 # DiscoverySource plugin (Run 2, 3, 5)
    base.py                # ABC + DiscoveryContext + SourceResult
    literal_list.py        # manual_additions
    holding_company.py     # subsidiary parser + audit log only
    dart_disclosure_filter.py  # treasury / spin_off / activist 통합 (Pain 1, 2)
    preferred_share_pair_seed.py  # pref spread enricher 의 entries 발견
    registry.py + factory.py
  enrichers/               # Enricher plugin (Run 5)
    base.py                # ABC + EnrichContext + EnrichedEntry
    nav_discount.py        # 지주사 NAV 할인
    spread_zscore.py       # 우선주 스프레드 z-score
    registry.py + factory.py
  audit/                   # G6 / G7 / G14 invariants + JSONL log (Run 4, 6)
    violation.py + log.py + citation.py + invariants.py
  application/             # build_universe orchestrator (Run 4)
    build_universe.py
  config/                  # self-contained YAML (Run 2~5)
    sources.yaml + enrichers.yaml + subsidiaries.yaml +
    preferred_pairs.yaml + manual_additions.yaml + exclusions.yaml
  main.py                  # CLI entry (Run 4)
  .guidelines/             # 패키지 컨벤션 6 markdown
```

## 외부 연결점

| 방향 | 인터페이스 | 위치 |
|---|---|---|
| 입력 (config) | `config/*.yaml` (sources, enrichers, subsidiaries, ...) | 패키지 내부 self-contained |
| 입력 (env) | `DART_API_KEY`, `KIS_APP_KEY` 등 | `.env` via `_boundary.load_env()` |
| 입력 (date) | KST `AsOfClock` | `domains/_shared/time/clock.py` |
| 입력 (universe 보조) | `governance/thresholds.yaml.universe.*` | Run 4 까지만; Run 5 이후 본 패키지 config 로 이전 완료 |
| 출력 (산출물) | `$TRAIL_TODAY/01-universe.json` (envelope schema `investment-stage1-universe-v1`) | `_boundary.resolve_path("trail_today")` |
| 출력 (audit log) | `$AUDIT_DIR/universe-violations/{date}.jsonl` (Run 4~) | JSONL append |
| 출력 (handoff) | stdout 1줄 stage handoff summary | `_boundary.emit_summary("stage1-universe", ...)` |
| 외부 도메인 호출 | 없음 — universe 는 *입력 단계*, 다음 stage 가 본 산출물 read | — |

## DDD bounded context 규약

- 다른 universe 모듈은 `infrastructure.*` / utils path helper / `os.environ` 직접 사용 금지 → `_boundary.py` 통과
- 다른 도메인 (`domains.screener`, `domains.alpha_factory`, ...) 의 내부 객체 import 금지
  - 예외: `domains._shared.*` (clock / calendar 공유 원시 + `ports/` Protocol + `adapters/disclosure_scan` shared scan)
- 외부 의존 추가: `_boundary.py` + `AGENTS.md` + `.guidelines/03-boundaries.md` 동시 갱신
- 패키지 외부 (다른 stage / skill) 가 본 패키지 산출물 사용 시 *산출 파일 + envelope schema* 만 인용, 내부 객체 (`UniverseEntry` 등) import 금지
- **shared disclosure scan (Wave5 / F-16)**: `DartDisclosureFilter` 의 per-item 매칭/dedup 스켈레톤은 `domains/_shared/adapters/disclosure_scan.scan_disclosures` 로 추출 — catalyst 3 detector 와 공유 (구 3중복제 소멸). `_boundary.dart_iter_disclosures` 를 `DisclosureSourcePort` 로 주입; window/retry/citation/매핑(`_build_entry`)은 source 잔류 (byte-parity). 패턴: `domains/screener/.guidelines/05-boundaries.md` "Ports & Adapters".

## 이전 대상 (Run 진행 중)

| 옛 모듈 | 대체 | Run |
|---|---|---|
| `domains.alpha_factory.universe` | `domains.universe.main` + `application.build_universe` | Run 4 |
| `domains.alpha_factory.stage1_nav_calc` | `domains.universe.enrichers.nav_discount` | Run 5 |
| `domains.alpha_factory.stage1_pref_spread` | `domains.universe.enrichers.spread_zscore` | Run 5 |
| `governance/thresholds.yaml.universe.*` | `domains/universe/config/*.yaml` | Run 2~5 점진적 이전 |

## 검증

```bash
# DDD boundary 위반 검사
grep -rn "from infrastructure\|import infrastructure" domains/universe/ | grep -v _boundary.py
# 결과 0 줄 (Run 2 이후 강제)

# 다른 도메인 import 검사
grep -rn "from domains\." domains/universe/ | grep -v "domains.universe\|domains._shared"
# 결과 0 줄
```
